"""Extract-transform-load from the Codeforces API into SQLite.

Pure transform functions (no I/O) are kept separate so they can be unit tested:
`transform_problems`, `transform_submissions`, `build_attempts`.
"""

import json
import re
import time
from collections import defaultdict
from typing import Callable

from . import cf_client, config, db, elo

# Verdicts that say nothing about whether the solver could solve the problem.
INELIGIBLE_VERDICTS = {None, "", "TESTING", "COMPILATION_ERROR", "SKIPPED", "SUBMITTED"}
GYM_CONTEST_FROM = 100000
IGNORED_TAGS = {"*special"}


def problem_key(contest_id, index) -> str | None:
    if contest_id is None or index is None:
        return None
    return f"{contest_id}{index}"


def _dedup_key(name: str, rating) -> str:
    return re.sub(r"\s+", " ", name.strip().lower()) + "|" + str(rating or "")


# ---------------------------------------------------------------- transforms

def transform_problems(raw: dict) -> list[dict]:
    """Turn `problemset.problems` output into clean, deduplicated problem rows."""
    solved = {
        problem_key(s.get("contestId"), s.get("index")): s.get("solvedCount", 0)
        for s in raw.get("problemStatistics", [])
    }
    rows: dict[str, dict] = {}
    for p in raw.get("problems", []):
        pid = problem_key(p.get("contestId"), p.get("index"))
        if pid is None or p.get("contestId", 0) >= GYM_CONTEST_FROM or p.get("type") != "PROGRAMMING":
            continue
        tags = sorted({t for t in p.get("tags", []) if t not in IGNORED_TAGS})
        rows[pid] = {
            "problem_id": pid,
            "contest_id": p["contestId"],
            "idx": p["index"],
            "name": p.get("name", "").strip(),
            "rating": p.get("rating"),
            "tags": tags,
            "solved_count": solved.get(pid, 0),
            "dedup_key": _dedup_key(p.get("name", ""), p.get("rating")),
        }
    return list(rows.values())


def transform_submissions(raw: list[dict], handle: str) -> list[dict]:
    """Keep submissions to regular (non-gym) problems; one row per submission id."""
    out: dict[int, dict] = {}
    for s in raw:
        prob = s.get("problem", {})
        pid = problem_key(prob.get("contestId"), prob.get("index"))
        if pid is None or prob.get("contestId", 0) >= GYM_CONTEST_FROM:
            continue
        out[s["id"]] = {
            "id": s["id"],
            "handle": handle,
            "problem_id": pid,
            "created_at": s["creationTimeSeconds"],
            "verdict": s.get("verdict"),
            "language": s.get("programmingLanguage"),
            "participant_type": (s.get("author") or {}).get("participantType"),
        }
    return list(out.values())


def build_attempts(submissions: list[dict], window: int = config.SOLVE_WINDOW_SECONDS) -> list[dict]:
    """Group a single user's submissions into one attempt per problem.

    The attempt starts at the first eligible submission (compilation errors and
    pending judgments are ignored). It counts as solved if an accepted
    submission arrives within `window` seconds of that start.
    """
    by_problem: dict[str, list[dict]] = defaultdict(list)
    for s in submissions:
        if s["verdict"] in INELIGIBLE_VERDICTS:
            continue
        by_problem[s["problem_id"]].append(s)

    attempts = []
    for pid, subs in by_problem.items():
        subs.sort(key=lambda s: (s["created_at"], s["id"]))
        first = subs[0]
        accepted = [s for s in subs if s["verdict"] == "OK"]
        first_ok = accepted[0]["created_at"] if accepted else None
        attempts.append({
            "handle": first["handle"],
            "problem_id": pid,
            "first_at": first["created_at"],
            "solved": int(first_ok is not None and first_ok - first["created_at"] <= window),
            "ever_solved": int(first_ok is not None),
            "solved_at": first_ok,
            "n_submissions": len(subs),
            "in_contest": int(first.get("participant_type") == "CONTESTANT"),
        })
    attempts.sort(key=lambda a: a["first_at"])
    return attempts


# ---------------------------------------------------------------- loaders

def refresh_problemset(conn, force: bool = False) -> int:
    """Download problem metadata at most once per day unless forced."""
    fetched = db.get_meta(conn, "problemset_fetched_at", 0)
    if not force and time.time() - fetched < config.PROBLEMSET_TTL_HOURS * 3600:
        return 0
    rows = transform_problems(cf_client.problemset())
    load_problems(conn, rows)
    db.set_meta(conn, "problemset_fetched_at", int(time.time()))
    conn.commit()
    return len(rows)


def load_problems(conn, rows: list[dict]) -> None:
    conn.executemany(
        """INSERT INTO problems(problem_id, contest_id, idx, name, rating, tags, solved_count, dedup_key)
           VALUES(:problem_id, :contest_id, :idx, :name, :rating, :tags_json, :solved_count, :dedup_key)
           ON CONFLICT(problem_id) DO UPDATE SET name=excluded.name, rating=excluded.rating,
             tags=excluded.tags, solved_count=excluded.solved_count, dedup_key=excluded.dedup_key""",
        [{**r, "tags_json": json.dumps(r["tags"])} for r in rows],
    )
    conn.executemany("DELETE FROM problem_tags WHERE problem_id=?", [(r["problem_id"],) for r in rows])
    conn.executemany(
        "INSERT OR IGNORE INTO problem_tags(problem_id, tag) VALUES(?, ?)",
        [(r["problem_id"], t) for r in rows for t in r["tags"]],
    )


def load_submissions(conn, rows: list[dict]) -> None:
    conn.executemany(
        """INSERT INTO submissions(id, handle, problem_id, created_at, verdict, language, participant_type)
           VALUES(:id, :handle, :problem_id, :created_at, :verdict, :language, :participant_type)
           ON CONFLICT(id) DO UPDATE SET verdict=excluded.verdict""",
        rows,
    )


def rebuild_attempts(conn, handle: str) -> int:
    subs = [dict(r) for r in conn.execute(
        "SELECT id, handle, problem_id, created_at, verdict, participant_type FROM submissions WHERE handle=?",
        (handle,),
    )]
    attempts = build_attempts(subs)
    conn.execute("DELETE FROM attempts WHERE handle=?", (handle,))
    conn.executemany(
        """INSERT INTO attempts(handle, problem_id, first_at, solved, ever_solved, solved_at, n_submissions, in_contest)
           VALUES(:handle, :problem_id, :first_at, :solved, :ever_solved, :solved_at, :n_submissions, :in_contest)""",
        attempts,
    )
    return len(attempts)


def _fetch_new_submissions(conn, handle: str) -> list[dict]:
    """Fetch only submissions newer than what is stored (plus any still pending)."""
    row = conn.execute(
        "SELECT last_submission_id FROM users WHERE handle=?", (handle,)
    ).fetchone()
    last_id = row["last_submission_id"] if row else 0
    pending = conn.execute(
        "SELECT MIN(id) AS m FROM submissions WHERE handle=? AND (verdict IS NULL OR verdict='TESTING')",
        (handle,),
    ).fetchone()["m"]
    stop_at = min(last_id, pending - 1) if pending else last_id

    if stop_at == 0:
        return cf_client.user_status(handle)

    collected, start, page = [], 1, 500
    while True:
        batch = cf_client.user_status(handle, start=start, count=page)
        fresh = [s for s in batch if s["id"] > stop_at]
        collected.extend(fresh)
        if len(fresh) < len(batch) or len(batch) < page:
            return collected
        start += page


def sync_user(conn, handle: str, progress: Callable[[str], None] = lambda stage: None,
              in_dataset: bool = False) -> dict:
    """Run the full pipeline for one handle and return a summary."""
    progress("problems")
    refresh_problemset(conn)

    progress("profile")
    info = cf_client.user_info([handle])[0]
    handle = info["handle"]  # canonical capitalisation
    conn.execute(
        """INSERT INTO users(handle, rating, max_rating, rank, max_rank, avatar, country, registered_at, in_dataset)
           VALUES(?,?,?,?,?,?,?,?,?)
           ON CONFLICT(handle) DO UPDATE SET rating=excluded.rating, max_rating=excluded.max_rating,
             rank=excluded.rank, max_rank=excluded.max_rank, avatar=excluded.avatar,
             country=excluded.country, in_dataset=MAX(users.in_dataset, excluded.in_dataset)""",
        (handle, info.get("rating"), info.get("maxRating"), info.get("rank"), info.get("maxRank"),
         info.get("titlePhoto"), info.get("country"), info.get("registrationTimeSeconds"), int(in_dataset)),
    )

    progress("submissions")
    rows = transform_submissions(_fetch_new_submissions(conn, handle), handle)
    load_submissions(conn, rows)

    progress("rating history")
    changes = cf_client.user_rating(handle)
    conn.executemany(
        """INSERT OR REPLACE INTO rating_changes(handle, contest_id, contest_name, rank, old_rating, new_rating, at)
           VALUES(?,?,?,?,?,?,?)""",
        [(handle, c["contestId"], c.get("contestName"), c.get("rank"), c.get("oldRating"),
          c.get("newRating"), c.get("ratingUpdateTimeSeconds")) for c in changes],
    )

    progress("attempts")
    n_attempts = rebuild_attempts(conn, handle)

    progress("topic ratings")
    elo.recompute_user(conn, handle)

    max_id = conn.execute("SELECT MAX(id) AS m FROM submissions WHERE handle=?", (handle,)).fetchone()["m"] or 0
    conn.execute("UPDATE users SET last_synced_at=?, last_submission_id=? WHERE handle=?",
                 (int(time.time()), max_id, handle))
    conn.commit()
    return {"handle": handle, "new_submissions": len(rows), "attempts": n_attempts,
            "contests": len(changes)}
