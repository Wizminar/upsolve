"""Business logic shared by the API: insights, recommendations, training plan."""

import hashlib
import json
import random
import sqlite3
import time
from datetime import datetime, timedelta

from . import config, elo
from .model import Predictor

RANKS = [  # Codeforces rank boundaries, used for labels next to every rank colour
    (0, "Newbie"), (1200, "Pupil"), (1400, "Specialist"), (1600, "Expert"),
    (1900, "Candidate Master"), (2100, "Master"), (2300, "International Master"),
    (2400, "Grandmaster"), (2600, "International Grandmaster"), (3000, "Legendary Grandmaster"),
]

_state_cache: dict[tuple[str, int], elo.PracticeState] = {}

# Estimates are made in "seen it" mode (the context of a contest problem): practice attempts
# only cover problems people chose to submit to, so practice-mode estimates are optimistic.
PREDICT_CONTEXT = 1


class NotSynced(Exception):
    pass


def rank_name(rating: float | None) -> str | None:
    if rating is None:
        return None
    name = RANKS[0][1]
    for lo, n in RANKS:
        if rating >= lo:
            name = n
    return name


def problem_url(contest_id: int, idx: str) -> str:
    return f"https://codeforces.com/problemset/problem/{contest_id}/{idx}"


def _user(conn, handle: str):
    row = conn.execute("SELECT * FROM users WHERE handle=?", (handle,)).fetchone()
    if not row or not row["last_synced_at"]:
        raise NotSynced(handle)
    return row


def practice_state(conn, handle: str) -> elo.PracticeState:
    user = _user(conn, handle)
    key = (user["handle"].lower(), user["last_synced_at"])
    if key not in _state_cache:
        _state_cache.clear() if len(_state_cache) > 64 else None
        _state_cache[key] = elo.state_for(conn, user["handle"])
    return _state_cache[key]


def confidence(n: int) -> str:
    return "low" if n < 5 else "medium" if n < 20 else "high"


# ------------------------------------------------------------------ insights

def profile(conn, handle: str) -> dict:
    u = _user(conn, handle)
    state = practice_state(conn, handle)
    stats = conn.execute(
        """SELECT COUNT(*) AS attempts, COALESCE(SUM(ever_solved),0) AS solved,
                  COALESCE(SUM(solved),0) AS solved_24h FROM attempts WHERE handle=?""", (u["handle"],)
    ).fetchone()
    subs = conn.execute("SELECT COUNT(*) AS n FROM submissions WHERE handle=?", (u["handle"],)).fetchone()["n"]
    return {
        "handle": u["handle"], "rating": u["rating"], "max_rating": u["max_rating"],
        "rank": u["rank"], "max_rank": u["max_rank"], "avatar": u["avatar"], "country": u["country"],
        "practice_rating": round(state.overall), "practice_rank": rank_name(state.overall),
        "submissions": subs, "attempts": stats["attempts"], "problems_solved": stats["solved"],
        "solved_within_24h": stats["solved_24h"], "last_synced_at": u["last_synced_at"],
        "model_source": Predictor.get().source,
    }


def topics(conn, handle: str) -> list[dict]:
    u = _user(conn, handle)
    state = practice_state(conn, handle)
    rows = conn.execute(
        "SELECT tag, rating, attempts, solved FROM topic_ratings WHERE handle=? AND tag != ?",
        (u["handle"], elo.OVERALL),
    ).fetchall()
    focus = set(training(conn, handle)["topics"])
    hardest = {r["tag"]: r["m"] for r in conn.execute(
        """SELECT t.tag, MAX(p.rating) AS m FROM attempts a JOIN problems p ON p.problem_id=a.problem_id
           JOIN problem_tags t ON t.problem_id=a.problem_id WHERE a.handle=? AND a.ever_solved=1 GROUP BY t.tag""",
        (u["handle"],))}
    out = []
    for r in rows:
        out.append({
            "tag": r["tag"], "rating": round(r["rating"]), "rank": rank_name(r["rating"]),
            "attempts": r["attempts"], "solved": r["solved"],
            "solve_rate": round(r["solved"] / r["attempts"], 3) if r["attempts"] else None,
            "relative": round(r["rating"] - state.overall),
            "confidence": confidence(r["attempts"]), "focus": r["tag"] in focus,
            "hardest_solved": hardest.get(r["tag"]),
        })
    out.sort(key=lambda t: -t["rating"])
    return out


def topic_history(conn, handle: str, tag: str) -> list[dict]:
    u = _user(conn, handle)
    rows = conn.execute(
        "SELECT at, rating FROM topic_rating_history WHERE handle=? AND tag=? ORDER BY at",
        (u["handle"], tag),
    ).fetchall()
    return [{"at": r["at"], "rating": round(r["rating"])} for r in rows]


def rating_history(conn, handle: str) -> list[dict]:
    u = _user(conn, handle)
    rows = conn.execute(
        "SELECT contest_id, contest_name, rank, old_rating, new_rating, at FROM rating_changes WHERE handle=? ORDER BY at",
        (u["handle"],),
    ).fetchall()
    return [dict(r) for r in rows]


def activity(conn, handle: str, days: int = 365) -> list[dict]:
    u = _user(conn, handle)
    since = int(time.time()) - days * 86400
    rows = conn.execute(
        """SELECT date(created_at, 'unixepoch', 'localtime') AS day, COUNT(*) AS submissions,
                  SUM(verdict='OK') AS accepted
           FROM submissions WHERE handle=? AND created_at>=? GROUP BY day ORDER BY day""",
        (u["handle"], since),
    ).fetchall()
    return [dict(r) for r in rows]


def attempts(conn, handle: str, limit: int = 50, tag: str | None = None) -> list[dict]:
    u = _user(conn, handle)
    q = """SELECT a.*, p.name, p.rating, p.tags, p.contest_id, p.idx FROM attempts a
           LEFT JOIN problems p ON p.problem_id=a.problem_id WHERE a.handle=?"""
    params: list = [u["handle"]]
    if tag:
        q += " AND a.problem_id IN (SELECT problem_id FROM problem_tags WHERE tag=?)"
        params.append(tag)
    q += " ORDER BY a.first_at DESC LIMIT ?"
    params.append(limit)
    out = []
    for r in conn.execute(q, params):
        d = dict(r)
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        d.pop("handle")
        out.append(d)
    return out


# ------------------------------------------------------------------ training settings

def training(conn, handle: str) -> dict:
    row = conn.execute("SELECT topics, weekly_target, updated_at FROM training WHERE handle=?", (handle,)).fetchone()
    if not row:
        return {"topics": [], "weekly_target": 5, "updated_at": None}
    return {"topics": json.loads(row["topics"]), "weekly_target": row["weekly_target"], "updated_at": row["updated_at"]}


def set_training(conn, handle: str, topics_: list[str], weekly_target: int) -> dict:
    u = _user(conn, handle)
    known = {r["tag"] for r in conn.execute("SELECT DISTINCT tag FROM problem_tags")}
    unknown = [t for t in topics_ if t not in known]
    if unknown:
        raise ValueError(f"Unknown topic(s): {', '.join(unknown)}")
    if len(set(topics_)) > config.MAX_FOCUS_TOPICS:
        raise ValueError(f"Choose at most {config.MAX_FOCUS_TOPICS} training topics")
    conn.execute(
        """INSERT INTO training(handle, topics, weekly_target, updated_at) VALUES(?,?,?,?)
           ON CONFLICT(handle) DO UPDATE SET topics=excluded.topics, weekly_target=excluded.weekly_target,
             updated_at=excluded.updated_at""",
        (u["handle"], json.dumps(sorted(set(topics_))), weekly_target, int(time.time())),
    )
    conn.commit()
    return training(conn, u["handle"])


# ------------------------------------------------------------------ recommendations

def _solved_and_tried(conn, handle: str):
    solved_keys, tried = set(), {}
    for r in conn.execute(
        """SELECT a.problem_id, a.ever_solved, a.first_at, p.dedup_key FROM attempts a
           LEFT JOIN problems p ON p.problem_id=a.problem_id WHERE a.handle=?""", (handle,)
    ):
        if r["ever_solved"]:
            solved_keys.add(r["dedup_key"] or r["problem_id"])
        else:
            tried[r["problem_id"]] = r["first_at"]
    return solved_keys, tried


def score_candidates(conn, handle: str, topic: str | None = None, widen: int = 0) -> list[dict]:
    """Score every unsolved rated problem near the user's level."""
    u = _user(conn, handle)
    state = practice_state(conn, handle)
    predictor = Predictor.get()
    solved_keys, tried = _solved_and_tried(conn, u["handle"])
    lo, hi = state.overall - 500 - 200 * widen, state.overall + 700 + 200 * widen
    q = "SELECT * FROM problems WHERE rating BETWEEN ? AND ?"
    params: list = [lo, hi]
    if topic:
        q += " AND problem_id IN (SELECT problem_id FROM problem_tags WHERE tag=?)"
        params.append(topic)
    rows = [r for r in conn.execute(q, params) if r["dedup_key"] not in solved_keys]
    if not rows:
        return []
    now = int(time.time())
    feats = []
    for r in rows:
        tags = json.loads(r["tags"])
        feats.append(state.features(r["rating"], tags, now, PREDICT_CONTEXT))
    probs = predictor.predict_many(feats)
    out = []
    for r, f, p in zip(rows, feats, probs):
        out.append({"row": r, "tags": json.loads(r["tags"]), "p": float(p), "features": f,
                    "tried_at": tried.get(r["problem_id"])})
    return out


def _weakness(state: elo.PracticeState, tag: str) -> float:
    st = state.tag(tag)
    if st["n"] == 0:
        return 0.3
    gap = (state.overall - st["r"]) / 300.0
    return max(0.0, min(1.0, gap)) * st["n"] / (st["n"] + 5)


def _reasons(state, c, focus: set[str]) -> list[dict]:
    r = c["row"]
    tags = c["tags"]
    reasons = []
    pct = round(c["p"] * 100)
    in_zone = config.TARGET_LOW <= c["p"] <= config.TARGET_HIGH
    reasons.append({"kind": "probability",
                    "text": f"{pct}% estimated chance, " + (
                        "inside your 50–70% stretch zone" if in_zone
                        else "easier than your 50–70% stretch zone" if c["p"] > config.TARGET_HIGH
                        else "harder than your 50–70% stretch zone")})
    diff = r["rating"] - round(state.overall)
    reasons.append({"kind": "difficulty",
                    "text": f"Rated {r['rating']}, {abs(diff)} {'above' if diff >= 0 else 'below'} your practice rating of {round(state.overall)}"})
    for t in tags:
        if t in focus:
            reasons.append({"kind": "focus", "text": f"Matches your training focus: {t}"})
    weak = [t for t in tags if t not in focus and state.tag(t)["a"] >= 5 and _weakness(state, t) > 0.25]
    if weak:
        t = weak[0]
        st = state.tag(t)
        reasons.append({"kind": "weak", "text": f"Builds a weaker topic: {t} ({round(st['r'])} from {st['a']} attempts)"})
    new = [t for t in tags if state.tag(t)["a"] == 0]
    if new:
        reasons.append({"kind": "new", "text": f"New topic for you: {new[0]}"})
    if c["tried_at"]:
        day = datetime.fromtimestamp(c["tried_at"]).strftime("%-d %b %Y")
        reasons.append({"kind": "upsolve", "text": f"Upsolve: you tried this on {day} and haven't solved it"})
    return reasons


def recommend(conn, handle: str, count: int = 5, topic: str | None = None, refresh: int = 0,
              log: bool = True) -> dict:
    u = _user(conn, handle)
    state = practice_state(conn, handle)
    focus = set(training(conn, u["handle"])["topics"])
    cands = []
    for widen in range(3):
        cands = score_candidates(conn, u["handle"], topic, widen)
        if sum(config.TARGET_LOW <= c["p"] <= config.TARGET_HIGH for c in cands) >= count:
            break
    seed = int(hashlib.sha1(f"{u['handle'].lower()}|{datetime.now():%Y-%m-%d}|{refresh}|{topic}".encode())
               .hexdigest()[:8], 16)
    rng = random.Random(seed)
    max_contest = max((c["row"]["contest_id"] for c in cands), default=1)

    for c in cands:
        p, tags = c["p"], c["tags"]
        in_zone = config.TARGET_LOW <= p <= config.TARGET_HIGH
        c["score"] = (
            (1.5 if in_zone else 0.0) - 4.0 * abs(p - 0.6)
            + (1.2 if focus & set(tags) else 0.0)
            + 0.8 * max((_weakness(state, t) for t in tags), default=0.0)
            + (0.5 if c["tried_at"] else 0.0)
            + 0.4 * (c["row"]["contest_id"] / max_contest)
            + rng.uniform(0, 0.6)
        )
    cands.sort(key=lambda c: -c["score"])

    picked, per_tag, contests = [], {}, set()
    for c in cands:
        if len(picked) >= count:
            break
        primary = c["tags"][:3]
        if c["row"]["contest_id"] in contests or any(per_tag.get(t, 0) >= 2 for t in primary):
            continue
        picked.append(c)
        contests.add(c["row"]["contest_id"])
        for t in primary:
            per_tag[t] = per_tag.get(t, 0) + 1

    predictor = Predictor.get()
    items = []
    now = int(time.time())
    for c in picked:
        r = c["row"]
        items.append({
            "problem_id": r["problem_id"], "name": r["name"], "rating": r["rating"],
            "rank": rank_name(r["rating"]), "tags": c["tags"], "url": problem_url(r["contest_id"], r["idx"]),
            "solved_count": r["solved_count"], "probability": round(c["p"], 4),
            "reasons": _reasons(state, c, focus), "upsolve": bool(c["tried_at"]),
        })
    if log and picked:
        _log_shown(conn, u["handle"], [(c["row"]["problem_id"], c["p"]) for c in picked], now, predictor.source)
    return {"handle": u["handle"], "practice_rating": round(state.overall), "source": predictor.source,
            "target": [config.TARGET_LOW, config.TARGET_HIGH], "stretch_zone": stretch_zone(state, predictor),
            "focus": sorted(focus), "items": items}


def stretch_zone(state, predictor) -> list[int]:
    """Difficulty range where a problem with no topic history scores 50–70%."""
    now = int(time.time())
    grid = list(range(800, 3601, 25))
    probs = predictor.predict_many([state.features(d, [], now, PREDICT_CONTEXT) for d in grid])
    inside = [d for d, p in zip(grid, probs) if config.TARGET_LOW <= p <= config.TARGET_HIGH]
    if not inside:
        nearest = min(zip(grid, probs), key=lambda x: abs(x[1] - 0.6))[0]
        return [nearest, nearest]
    return [min(inside), max(inside)]


def _log_shown(conn, handle, items, now, source):
    """Remember what was shown so later syncs can check the estimates. Best effort: never
    make the user wait for a database lock held by a running import."""
    conn.execute("PRAGMA busy_timeout=500")
    try:
        conn.executemany(
            "INSERT OR IGNORE INTO recommendation_log(handle, problem_id, shown_at, probability, source) VALUES(?,?,?,?,?)",
            [(handle, pid, now, p, source) for pid, p in items],
        )
        conn.commit()
    except sqlite3.OperationalError:
        conn.rollback()
    finally:
        conn.execute("PRAGMA busy_timeout=30000")


def predict(conn, handle: str, problem_id: str) -> dict:
    u = _user(conn, handle)
    r = conn.execute("SELECT * FROM problems WHERE problem_id=?", (problem_id,)).fetchone()
    if not r:
        raise KeyError(problem_id)
    if r["rating"] is None:
        raise ValueError("This problem has no difficulty rating, so no estimate can be made")
    state = practice_state(conn, handle)
    tags = json.loads(r["tags"])
    f = state.features(r["rating"], tags, int(time.time()), PREDICT_CONTEXT)
    predictor = Predictor.get()
    p = float(predictor.predict_many([f])[0])
    _, tried = _solved_and_tried(conn, u["handle"])
    focus = set(training(conn, u["handle"])["topics"])
    return {"problem_id": problem_id, "name": r["name"], "rating": r["rating"], "tags": tags,
            "probability": round(p, 4), "elo_probability": round(state.elo_probability(r["rating"], tags), 4),
            "source": predictor.source,
            "contributions": {k: round(v, 4) for k, v in predictor.contributions(f).items()},
            "reasons": _reasons(state, {"row": r, "tags": tags, "p": p, "tried_at": tried.get(problem_id)}, focus)}


def recommendation_feedback(conn, handle: str) -> dict:
    """How did previously shown recommendations turn out? (the adaptive loop's report card)"""
    u = _user(conn, handle)
    rows = conn.execute(
        """SELECT l.problem_id, l.probability, l.shown_at, a.first_at, a.solved, a.ever_solved
           FROM recommendation_log l LEFT JOIN attempts a
             ON a.handle=l.handle AND a.problem_id=l.problem_id AND a.first_at >= l.shown_at - 60
           WHERE l.handle=?""", (u["handle"],),
    ).fetchall()
    tried = [r for r in rows if r["first_at"] is not None]
    return {
        "shown": len(rows), "attempted": len(tried),
        "solved": sum(r["ever_solved"] for r in tried),
        "mean_predicted": round(sum(r["probability"] for r in tried) / len(tried), 4) if tried else None,
        "observed_rate": round(sum(r["ever_solved"] for r in tried) / len(tried), 4) if tried else None,
    }


# ------------------------------------------------------------------ weekly plan

def week_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now()
    start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=7)


def plan(conn, handle: str) -> dict:
    u = _user(conn, handle)
    settings = training(conn, u["handle"])
    focus, target = settings["topics"], settings["weekly_target"]
    start, end = week_bounds()
    s_ts, e_ts = int(start.timestamp()), int(end.timestamp())

    solved_rows = conn.execute(
        """SELECT a.problem_id, a.solved_at, p.name, p.rating, p.tags FROM attempts a
           LEFT JOIN problems p ON p.problem_id=a.problem_id
           WHERE a.handle=? AND a.solved_at>=? AND a.solved_at<? ORDER BY a.solved_at""",
        (u["handle"], s_ts, e_ts),
    ).fetchall()
    solved_week = []
    for r in solved_rows:
        tags = json.loads(r["tags"]) if r["tags"] else []
        solved_week.append({"problem_id": r["problem_id"], "name": r["name"], "rating": r["rating"], "tags": tags,
                            "solved_at": r["solved_at"], "counts": not focus or bool(set(tags) & set(focus))})
    progress = sum(s["counts"] for s in solved_week)

    # Build a deterministic slate for the week: easier early, stretching later.
    rng = random.Random(f"{u['handle'].lower()}|{start:%Y-%m-%d}")
    pools = []
    for t in (focus or [None]):
        cands = [c for c in score_candidates(conn, u["handle"], t, 1) if 0.4 <= c["p"] <= 0.8]
        rng.shuffle(cands)
        pools.append(cands)
    used, slots = set(), []
    solved_ids = {s["problem_id"] for s in solved_week}
    for k in range(target):
        want = 0.7 - 0.2 * (k / max(target - 1, 1))
        pool = pools[k % len(pools)]
        best = min((c for c in pool if c["row"]["problem_id"] not in used),
                   key=lambda c: abs(c["p"] - want), default=None)
        day = start + timedelta(days=min(6, round(k * 7 / target)))
        slot = {"day": day.strftime("%Y-%m-%d"), "weekday": day.strftime("%a"), "target_probability": round(want, 2)}
        if best:
            r = best["row"]
            used.add(r["problem_id"])
            slot.update({"problem_id": r["problem_id"], "name": r["name"], "rating": r["rating"],
                         "tags": best["tags"], "probability": round(best["p"], 4),
                         "url": problem_url(r["contest_id"], r["idx"]),
                         "done": r["problem_id"] in solved_ids})
        slots.append(slot)

    days = []
    for i in range(7):
        d = start + timedelta(days=i)
        key = d.strftime("%Y-%m-%d")
        days.append({"day": key, "weekday": d.strftime("%a"),
                     "solved": [s for s in solved_week if datetime.fromtimestamp(s["solved_at"]).strftime("%Y-%m-%d") == key],
                     "planned": [s for s in slots if s["day"] == key]})
    return {"handle": u["handle"], "week_start": start.strftime("%Y-%m-%d"), "focus": focus,
            "weekly_target": target, "progress": progress, "days": days}
