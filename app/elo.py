"""Elo-style practice ratings: one overall rating plus one rating per topic tag.

Every rated attempt is treated as a game between the user and the problem,
whose Codeforces difficulty is its fixed rating.

Why ratings are anchored: people mostly submit to problems they expect to
solve, so a plain Elo rating fed by practice attempts drifts far above the
user's real level (a 1500 solver who solves 90% of the 1500s they try looks
like a 1900). Upsolve therefore anchors the overall rating to the official
contest rating at the time of each attempt and learns a *form offset* on top,
which decays a little after every attempt so it reflects recent practice.
Each topic learns its own decaying offset relative to the overall rating.

The state is replayed in chronological order, so a snapshot taken before an
attempt only uses earlier evidence. The same replay produces the classifier's
training features.
"""

import bisect
import json
import math
import time
from collections import deque
from datetime import datetime, timezone

OVERALL = "__overall__"
UNRATED_BASE = 1200.0
FORM_DECAY = 0.98          # per attempt, for users with a contest rating
FORM_DECAY_UNRATED = 0.995  # unrated users have no anchor, so form carries more
TOPIC_DECAY = 0.995
FEATURE_NAMES = [
    "elo_logit", "gap_overall", "gap_weakest_tag", "tag_evidence", "tag_solve_rate",
    "recent_solve_rate", "log_total_attempts", "log_days_since_last", "n_tags",
    "difficulty", "in_contest",
]


def expected(rating: float, difficulty: float) -> float:
    return 1.0 / (1.0 + 10 ** ((difficulty - rating) / 400.0))


def _k(n: int, high: float, low: float) -> float:
    return max(low, high / math.sqrt(1 + n))


class ContestTimeline:
    """Official rating as a step function of time."""

    def __init__(self, changes: list[tuple[int, int]]):
        changes = sorted((at, r) for at, r in changes if at is not None and r is not None)
        self.times = [c[0] for c in changes]
        self.ratings = [c[1] for c in changes]

    def at(self, ts: int) -> float | None:
        if not self.times:
            return None
        i = bisect.bisect_right(self.times, ts) - 1
        # Before the first rated contest, the first result is the best guess of the level.
        return float(self.ratings[max(i, 0)])

    @property
    def rated(self) -> bool:
        return bool(self.times)


class PracticeState:
    def __init__(self, timeline: ContestTimeline | None = None):
        self.timeline = timeline or ContestTimeline([])
        self.base = UNRATED_BASE
        self.form = 0.0
        self.n = 0      # games, including contest problems left unsolved
        self.a = 0      # real attempts (problems the user submitted to)
        self.s = 0
        self.tags: dict[str, dict] = {}
        self.last_at: int | None = None
        self.recent: deque = deque(maxlen=20)

    def set_time(self, ts: int) -> None:
        r = self.timeline.at(ts)
        self.base = r if r is not None else UNRATED_BASE

    @property
    def overall(self) -> float:
        return self.base + self.form

    # -- reading -----------------------------------------------------------
    def tag(self, t: str) -> dict:
        st = self.tags.get(t)
        if not st:
            return {"r": self.overall, "n": 0, "a": 0, "s": 0}
        return {"r": self.overall + st["d"], "n": st["n"], "a": st["a"], "s": st["s"]}

    def effective_rating(self, tags: list[str]) -> float:
        """Overall rating shifted towards topic ratings, weighted by evidence."""
        if not tags:
            return self.overall
        shift = 0.0
        for t in tags:
            st = self.tags.get(t)
            if st:
                shift += st["n"] / (st["n"] + 5) * st["d"]
        return self.overall + shift / len(tags)

    def elo_probability(self, difficulty: float, tags: list[str]) -> float:
        return expected(self.effective_rating(tags), difficulty)

    def features(self, difficulty: float, tags: list[str], at: int, in_contest: int = 0) -> list[float]:
        p = min(max(self.elo_probability(difficulty, tags), 1e-4), 1 - 1e-4)
        tag_states = [self.tag(t) for t in tags] or [{"r": self.overall, "n": 0, "s": 0}]
        weakest = min(st["r"] for st in tag_states)
        days = (at - self.last_at) / 86400 if self.last_at else 365.0
        recent = (sum(self.recent) + 1) / (len(self.recent) + 2)
        return [
            math.log(p / (1 - p)),
            (difficulty - self.overall) / 400.0,
            (difficulty - weakest) / 400.0,
            sum(math.log1p(st["n"]) for st in tag_states) / len(tag_states),
            sum((st["s"] + 1) / (st["n"] + 2) for st in tag_states) / len(tag_states),
            recent,
            math.log1p(self.n),
            math.log1p(max(days, 0.0)),
            float(len(tags)),
            (difficulty - 1500.0) / 1000.0,
            float(in_contest),
        ]

    # -- writing -----------------------------------------------------------
    def update(self, difficulty: float, tags: list[str], solved: int, at: int, implicit: int = 0) -> None:
        decay = FORM_DECAY if self.timeline.rated else FORM_DECAY_UNRATED
        self.form = (self.form + _k(self.n, 80, 16) * (solved - expected(self.overall, difficulty))) * decay
        self.n += 1
        self.a += 0 if implicit else 1
        self.s += solved
        for t in tags:
            st = self.tags.setdefault(t, {"d": 0.0, "n": 0, "a": 0, "s": 0})
            r = self.overall + st["d"]
            st["d"] = (st["d"] + _k(st["n"], 80, 16) * (solved - expected(r, difficulty))) * TOPIC_DECAY
            st["n"] += 1
            st["a"] += 0 if implicit else 1
            st["s"] += solved
        # Topic ratings describe relative strength: keep their evidence-weighted mean offset at zero,
        # so a general upward drift is absorbed by the overall form, not by every topic at once.
        total = sum(st["n"] for st in self.tags.values())
        if total:
            mean = sum(st["n"] * st["d"] for st in self.tags.values()) / total
            for st in self.tags.values():
                st["d"] -= mean
        self.recent.append(solved)
        self.last_at = at


def load_attempt_rows(conn, handle: str, implicit: bool = True) -> list[dict]:
    """Rated attempts in time order, plus implicit contest failures.

    Attempt data alone is heavily biased: people mostly submit to problems they expect to
    solve, so failures on hard problems are rare. In a rated contest, however, the user saw
    every problem. Each rated problem of a contest they took part in that they did not
    attempt during that contest is added as an unsolved game (`implicit=1`).
    """
    rows = [{**dict(r), "tags": json.loads(r["tags"]), "implicit": 0} for r in conn.execute(
        """SELECT a.problem_id, a.first_at, a.solved, a.in_contest, p.rating, p.tags
           FROM attempts a JOIN problems p ON p.problem_id = a.problem_id
           WHERE a.handle=? AND p.rating IS NOT NULL""",
        (handle,),
    )]
    if implicit:
        rows.extend(_implicit_contest_failures(conn, handle))
    rows.sort(key=lambda r: (r["first_at"], r["implicit"]))
    return rows


def _implicit_contest_failures(conn, handle: str) -> list[dict]:
    # When did the user start each contest? Use their first contestant submission, else
    # assume the round ended at most 3 h before its rating update.
    starts = {r["contest_id"]: r["t"] for r in conn.execute(
        """SELECT p.contest_id, MIN(s.created_at) AS t FROM submissions s
           JOIN problems p ON p.problem_id = s.problem_id
           WHERE s.handle=? AND s.participant_type='CONTESTANT' GROUP BY p.contest_id""", (handle,))}
    for r in conn.execute("SELECT contest_id, at FROM rating_changes WHERE handle=?", (handle,)):
        if r["contest_id"] not in starts and r["at"]:
            starts[r["contest_id"]] = r["at"] - 3 * 3600
    if not starts:
        return []
    tried_in_contest = {r["problem_id"] for r in conn.execute(
        "SELECT problem_id FROM attempts WHERE handle=? AND in_contest=1", (handle,))}
    solved_at = {r["problem_id"]: r["solved_at"] for r in conn.execute(
        "SELECT problem_id, solved_at FROM attempts WHERE handle=? AND ever_solved=1", (handle,))}
    marks = ",".join("?" * len(starts))
    out = []
    for p in conn.execute(
        f"SELECT problem_id, contest_id, rating, tags FROM problems WHERE rating IS NOT NULL AND contest_id IN ({marks})",
        list(starts),
    ):
        start = starts[p["contest_id"]]
        if p["problem_id"] in tried_in_contest or solved_at.get(p["problem_id"], start + 1) <= start:
            continue
        out.append({"problem_id": p["problem_id"], "first_at": start + 2 * 3600,
                    "solved": 0, "in_contest": 1, "rating": p["rating"], "tags": json.loads(p["tags"]),
                    "implicit": 1})
    return out


def load_timeline(conn, handle: str) -> ContestTimeline:
    return ContestTimeline([(r["at"], r["new_rating"]) for r in conn.execute(
        "SELECT at, new_rating FROM rating_changes WHERE handle=?", (handle,))])


def replay(rows: list[dict], timeline: ContestTimeline | None = None, on_attempt=None,
           now: int | None = None) -> tuple[PracticeState, list[tuple]]:
    """Replay attempts. Returns the final state (as of `now`) and daily history points."""
    state = PracticeState(timeline)
    daily: dict[tuple[str, str], tuple[int, float]] = {}
    for row in rows:
        state.set_time(row["first_at"])
        if on_attempt:
            on_attempt(state, row)
        state.update(row["rating"], row["tags"], row["solved"], row["first_at"], row.get("implicit", 0))
        day = datetime.fromtimestamp(row["first_at"], timezone.utc).strftime("%Y-%m-%d")
        daily[(OVERALL, day)] = (row["first_at"], state.overall)
        for t in row["tags"]:
            daily[(t, day)] = (row["first_at"], state.overall + state.tags[t]["d"])
    state.set_time(now or int(time.time()))
    history = [(tag, at, r) for (tag, _), (at, r) in daily.items()]
    return state, history


def state_for(conn, handle: str) -> PracticeState:
    state, _ = replay(load_attempt_rows(conn, handle), load_timeline(conn, handle))
    return state


def recompute_user(conn, handle: str) -> PracticeState:
    state, history = replay(load_attempt_rows(conn, handle), load_timeline(conn, handle))
    now = int(time.time())
    conn.execute("DELETE FROM topic_ratings WHERE handle=?", (handle,))
    conn.execute("DELETE FROM topic_rating_history WHERE handle=?", (handle,))
    conn.executemany(
        "INSERT INTO topic_ratings(handle, tag, rating, attempts, solved, updated_at) VALUES(?,?,?,?,?,?)",
        [(handle, t, state.overall + st["d"], st["a"], st["s"], now) for t, st in state.tags.items() if st["a"]]
        + [(handle, OVERALL, state.overall, state.a, state.s, now)],
    )
    conn.executemany(
        "INSERT INTO topic_rating_history(handle, tag, at, rating) VALUES(?,?,?,?)",
        [(handle, t, at, r) for t, at, r in history],
    )
    return state
