"""FastAPI application: versioned REST API, plugin host, and the static web app."""

import json
import threading
from contextlib import asynccontextmanager
import time
from typing import Annotated

from fastapi import Body, Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, cf_client, coach, config, db, etl, plugins, text_view
from . import schemas as S
from .model import Predictor

DESCRIPTION = """
Upsolve recommends Codeforces practice problems from a user's own submission history.

**Workflow:** `POST /api/v1/users/{handle}/sync` starts an import, poll
`GET /api/v1/users/{handle}/sync` until `status` is `done`, then read insights and
recommendations. All other user endpoints return **404** until the handle is synced.

**Plugins** run inside the Upsolve web app. They call this API through the plugin host
and can save their own data with the `/plugins/{plugin_id}/store` endpoints.
See `docs/PLUGINS.md`.
"""

TAGS = [
    {"name": "sync", "description": "Import a handle from Codeforces (ETL)"},
    {"name": "insights", "description": "Profile, topic strengths, histories, activity"},
    {"name": "coach", "description": "Recommendations, predictions and training plans (adaptive core)"},
    {"name": "catalog", "description": "Problems, topics and the model report"},
    {"name": "plugins", "description": "Plugin registry and plugin data store"},
]

@asynccontextmanager
async def lifespan(_app):
    with db.session() as conn:  # creates tables; jobs cut off by a restart are marked failed
        conn.execute("UPDATE sync_jobs SET status='failed', message='Server restarted' "
                     "WHERE status IN ('queued','running')")
    yield


app = FastAPI(title="Upsolve API", lifespan=lifespan, version=__version__, description=DESCRIPTION, openapi_tags=TAGS,
              docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/v1/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def _revalidate_assets(request: Request, call_next):
    """Ask browsers to revalidate pages, app and plugin files so edits show up on reload."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response

HANDLE_RE = r"^[A-Za-z0-9_.\-]{3,24}$"
Handle = Annotated[str, Path(pattern=HANDLE_RE, description="Codeforces handle (case-insensitive)",
                             examples=["tourist"])]


def get_conn():
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[object, Depends(get_conn)]




@app.exception_handler(coach.NotSynced)
def _not_synced(_: Request, exc: coach.NotSynced):
    h = str(exc)
    return JSONResponse(status_code=404, content={
        "detail": f"'{h}' has not been synced yet. Start a sync with POST /api/v1/users/{h}/sync."})


# ------------------------------------------------------------------ sync

_running: set[str] = set()
_running_lock = threading.Lock()


def _job(conn, job_id: int) -> dict:
    return dict(conn.execute("SELECT * FROM sync_jobs WHERE id=?", (job_id,)).fetchone())


def _run_sync(job_id: int, handle: str):
    conn = db.connect()
    try:
        def progress(stage):
            conn.execute("UPDATE sync_jobs SET stage=? WHERE id=?", (stage, job_id))
            conn.commit()

        conn.execute("UPDATE sync_jobs SET status='running', started_at=? WHERE id=?", (int(time.time()), job_id))
        conn.commit()
        summary = etl.sync_user(conn, handle, progress)
        conn.execute("UPDATE sync_jobs SET status='done', stage=NULL, finished_at=?, new_submissions=?, handle=?, "
                     "message=? WHERE id=?",
                     (int(time.time()), summary["new_submissions"], summary["handle"],
                      f"{summary['attempts']} attempts, {summary['contests']} rated contests", job_id))
    except cf_client.HandleNotFound:
        conn.execute("UPDATE sync_jobs SET status='failed', finished_at=?, message=? WHERE id=?",
                     (int(time.time()), f"No Codeforces user is called '{handle}'. Check the spelling.", job_id))
    except Exception as exc:  # report every failure through the job record
        conn.execute("UPDATE sync_jobs SET status='failed', finished_at=?, message=? WHERE id=?",
                     (int(time.time()), f"Sync stopped: {exc}", job_id))
    finally:
        conn.commit()
        conn.close()
        with _running_lock:
            _running.discard(handle.lower())


@app.post("/api/v1/users/{handle}/sync", response_model=S.SyncJob, status_code=202, tags=["sync"],
          summary="Start importing a handle")
def start_sync(handle: Handle, conn: Conn):
    """Queues an incremental import: profile, new submissions, rating history and problem
    metadata (cached for 24 h). Requests to Codeforces are paced at one per ~2 s, so a first
    import of a large history can take a minute. If a sync is already running it is returned."""
    with _running_lock:
        if handle.lower() in _running:
            row = conn.execute("SELECT * FROM sync_jobs WHERE handle=? ORDER BY id DESC LIMIT 1", (handle,)).fetchone()
            return dict(row)
        _running.add(handle.lower())
    cur = conn.execute("INSERT INTO sync_jobs(handle, status, stage) VALUES(?, 'queued', 'queued')", (handle,))
    conn.commit()
    job_id = cur.lastrowid
    threading.Thread(target=_run_sync, args=(job_id, handle), daemon=True).start()
    return _job(conn, job_id)


@app.get("/api/v1/users/{handle}/sync", response_model=S.SyncJob, tags=["sync"], summary="Latest sync status")
def sync_status(handle: Handle, conn: Conn):
    row = conn.execute("SELECT * FROM sync_jobs WHERE handle=? ORDER BY id DESC LIMIT 1", (handle,)).fetchone()
    if not row:
        raise HTTPException(404, f"No sync has been started for '{handle}'.")
    return dict(row)


@app.get("/api/v1/users", tags=["sync"], summary="List synced handles")
def list_users(conn: Conn, include_dataset: bool = False) -> list[dict]:
    q = "SELECT handle, rating, rank, last_synced_at, in_dataset FROM users WHERE last_synced_at IS NOT NULL"
    if not include_dataset:
        q += " AND in_dataset=0"
    return [dict(r) for r in conn.execute(q + " ORDER BY last_synced_at DESC")]


# ------------------------------------------------------------------ insights

@app.get("/api/v1/users/{handle}/profile", response_model=S.Profile, tags=["insights"])
def get_profile(handle: Handle, conn: Conn):
    return coach.profile(conn, handle)


@app.get("/api/v1/users/{handle}/topics", response_model=list[S.Topic], tags=["insights"],
         summary="Topic strengths with evidence counts")
def get_topics(handle: Handle, conn: Conn):
    return coach.topics(conn, handle)


@app.get("/api/v1/users/{handle}/topics/{tag}/history", response_model=list[S.HistoryPoint], tags=["insights"],
         summary="Daily topic rating trend")
def get_topic_history(handle: Handle, tag: str, conn: Conn):
    """Use the tag `__overall__` for the overall practice rating."""
    return coach.topic_history(conn, handle, tag)


@app.get("/api/v1/users/{handle}/rating-history", response_model=list[S.RatingChange], tags=["insights"],
         summary="Official contest rating history")
def get_rating_history(handle: Handle, conn: Conn):
    return coach.rating_history(conn, handle)


@app.get("/api/v1/users/{handle}/activity", response_model=list[S.ActivityDay], tags=["insights"],
         summary="Submissions per day")
def get_activity(handle: Handle, conn: Conn, days: Annotated[int, Query(ge=7, le=730)] = 365):
    return coach.activity(conn, handle, days)


@app.get("/api/v1/users/{handle}/attempts", tags=["insights"], summary="Recent attempts (grouped submissions)")
def get_attempts(handle: Handle, conn: Conn, limit: Annotated[int, Query(ge=1, le=500)] = 50,
                 tag: str | None = None) -> list[dict]:
    return coach.attempts(conn, handle, limit, tag)


# ------------------------------------------------------------------ coach

@app.get("/api/v1/users/{handle}/recommendations", response_model=S.Recommendations, tags=["coach"],
         summary="Daily problem recommendations")
def get_recommendations(handle: Handle, conn: Conn, count: Annotated[int, Query(ge=1, le=20)] = 5,
                        topic: str | None = None, refresh: Annotated[int, Query(ge=0)] = 0):
    """Problems targeting a 50–70% estimated solve probability, ranked by training focus,
    weak topics, upsolve opportunities and recency. The list is stable for a day; pass a
    different `refresh` number for a new set."""
    return coach.recommend(conn, handle, count, topic, refresh)


@app.get("/api/v1/users/{handle}/predict/{problem_id}", response_model=S.Prediction, tags=["coach"],
         summary="Estimate the chance of solving one problem")
def get_prediction(handle: Handle, problem_id: Annotated[str, Path(examples=["1520A"])], conn: Conn):
    try:
        return coach.predict(conn, handle, problem_id.upper())
    except KeyError:
        raise HTTPException(404, f"Problem {problem_id} is not in the problem set.")
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get("/api/v1/users/{handle}/feedback", response_model=S.Feedback, tags=["coach"],
         summary="How past recommendations turned out")
def get_feedback(handle: Handle, conn: Conn):
    return coach.recommendation_feedback(conn, handle)


@app.get("/api/v1/users/{handle}/training", response_model=S.TrainingOut, tags=["coach"])
def get_training(handle: Handle, conn: Conn):
    return coach.training(conn, handle)


@app.put("/api/v1/users/{handle}/training", response_model=S.TrainingOut, tags=["coach"],
         summary="Set up to two training topics and a weekly solve target")
def put_training(handle: Handle, body: S.TrainingSettings, conn: Conn):
    try:
        return coach.set_training(conn, handle, body.topics, body.weekly_target)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get("/api/v1/users/{handle}/plan", response_model=S.Plan, tags=["coach"], summary="This week's training plan")
def get_plan(handle: Handle, conn: Conn):
    return coach.plan(conn, handle)


# ------------------------------------------------------------------ catalog

@app.get("/api/v1/topics", tags=["catalog"], summary="All topic tags with problem counts")
def list_topics(conn: Conn) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT tag, COUNT(*) AS problems FROM problem_tags GROUP BY tag ORDER BY problems DESC")]


@app.get("/api/v1/problems", tags=["catalog"], summary="Search the problem set")
def list_problems(conn: Conn, tag: str | None = None, min_rating: int = 800, max_rating: int = 3500,
                  limit: Annotated[int, Query(ge=1, le=200)] = 50) -> list[dict]:
    q = "SELECT * FROM problems WHERE rating BETWEEN ? AND ?"
    p: list = [min_rating, max_rating]
    if tag:
        q += " AND problem_id IN (SELECT problem_id FROM problem_tags WHERE tag=?)"
        p.append(tag)
    rows = conn.execute(q + " ORDER BY contest_id DESC LIMIT ?", p + [limit]).fetchall()
    return [{**dict(r), "tags": json.loads(r["tags"]), "url": coach.problem_url(r["contest_id"], r["idx"])}
            for r in rows]


@app.get("/api/v1/model", tags=["catalog"], summary="Model report: evaluation metrics and calibration")
def model_report() -> dict:
    p = Predictor.get()
    if not p.artifact:
        return {"source": "elo", "message": "No trained model found; Elo estimates are in use."}
    a = p.artifact
    return {"source": "model", "trained_at": a["trained_at"], "split": a["split"], "metrics": a["metrics"],
            "coefficients": dict(zip(a["features"], a["coef"]))}


@app.get("/api/v1/health", tags=["catalog"])
def health(conn: Conn) -> dict:
    return {"status": "ok", "version": __version__, "model": Predictor.get().source,
            "problems": conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]}


# ------------------------------------------------------------------ plugins

PluginId = Annotated[str, Path(pattern=plugins.ID_RE.pattern, examples=["rival"])]
Scope = Annotated[str, Path(pattern=r"^(_global|[A-Za-z0-9_.\-]{3,24})$",
                            description="A handle, or `_global` for data not tied to a user")]
Key = Annotated[str, Path(pattern=r"^[A-Za-z0-9_.\-]{1,64}$")]


def _plugin(conn, plugin_id):
    found = next((p for p in plugins.discover(conn) if p["id"] == plugin_id), None)
    if not found:
        raise HTTPException(404, f"No plugin called '{plugin_id}' is installed.")
    return found


@app.get("/api/v1/plugins", response_model=list[S.PluginInfo], tags=["plugins"], summary="Installed plugins")
def list_plugins(conn: Conn):
    return plugins.discover(conn)


@app.put("/api/v1/plugins/{plugin_id}", response_model=S.PluginInfo, tags=["plugins"], summary="Turn a plugin on or off")
def toggle_plugin(plugin_id: PluginId, body: S.PluginToggle, conn: Conn):
    _plugin(conn, plugin_id)
    plugins.set_enabled(conn, plugin_id, body.enabled)
    return _plugin(conn, plugin_id)


@app.get("/api/v1/plugins/{plugin_id}/store/{scope}", tags=["plugins"], summary="All stored values")
def store_list(plugin_id: PluginId, scope: Scope, conn: Conn) -> dict:
    _plugin(conn, plugin_id)
    return plugins.store_list(conn, plugin_id, scope)


@app.get("/api/v1/plugins/{plugin_id}/store/{scope}/{key}", response_model=S.StoreItem, tags=["plugins"])
def store_get(plugin_id: PluginId, scope: Scope, key: Key, conn: Conn):
    _plugin(conn, plugin_id)
    value, at = plugins.store_get(conn, plugin_id, scope, key)
    if at is None:
        raise HTTPException(404, f"No value stored under '{key}'.")
    return {"key": key, "value": value, "updated_at": at}


@app.put("/api/v1/plugins/{plugin_id}/store/{scope}/{key}", response_model=S.StoreItem, tags=["plugins"])
def store_put(plugin_id: PluginId, scope: Scope, key: Key, body: S.StoreValue, conn: Conn):
    _plugin(conn, plugin_id)
    try:
        at = plugins.store_put(conn, plugin_id, scope, key, body.value)
    except ValueError as exc:
        raise HTTPException(413, str(exc))
    return {"key": key, "value": body.value, "updated_at": at}


@app.delete("/api/v1/plugins/{plugin_id}/store/{scope}/{key}", status_code=204, tags=["plugins"])
def store_delete(plugin_id: PluginId, scope: Scope, key: Key, conn: Conn):
    _plugin(conn, plugin_id)
    if not plugins.store_delete(conn, plugin_id, scope, key):
        raise HTTPException(404, f"No value stored under '{key}'.")


# ------------------------------------------------------------------ web app

@app.get("/text/{handle}", response_class=HTMLResponse, include_in_schema=False)
def text_page(handle: Handle, conn: Conn):
    """Plain HTML summary, readable in text browsers such as lynx."""
    return text_view.render(conn, handle)


config.PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/plugin-files", StaticFiles(directory=config.PLUGINS_DIR), name="plugin-files")
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(config.STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


@app.get("/", include_in_schema=False)
@app.get("/u/{handle}", include_in_schema=False)
@app.get("/u/{handle}/{view}", include_in_schema=False)
def spa(handle: str | None = None, view: str | None = None):
    return FileResponse(config.STATIC_DIR / "index.html")
