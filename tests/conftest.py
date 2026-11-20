"""Test fixtures: an isolated database seeded with synthetic Codeforces data (no network)."""

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DAY = 86400
T0 = 1_700_000_000


def make_problem(cid, idx, rating, tags, name=None):
    return {"contestId": cid, "index": idx, "name": name or f"Problem {cid}{idx}", "type": "PROGRAMMING",
            "rating": rating, "tags": tags}


PROBLEMS = {
    "problems": [
        make_problem(1000, "A", 800, ["implementation"]),
        make_problem(1000, "B", 1200, ["greedy", "math"]),
        make_problem(1000, "C", 1500, ["dp"]),
        make_problem(1000, "D", 1900, ["graphs"]),                   # seen in the contest, never tried
        make_problem(1001, "A", 900, ["implementation", "strings"]),
        make_problem(1001, "B", 1300, ["greedy"]),
        make_problem(1001, "C", 1600, ["dp", "graphs"]),
        make_problem(1002, "A", 1000, ["math"]),
        make_problem(1002, "B", 1400, ["graphs"]),
        make_problem(1002, "C", 1700, ["dp", "greedy"]),
        make_problem(1003, "A", 1100, ["strings"]),
        make_problem(1003, "B", 1450, ["graphs", "*special"]),
        make_problem(1003, "C", 1550, ["math", "number theory"]),
        make_problem(1004, "D", None, ["dp"]),                       # unrated
        make_problem(100500, "A", 1200, ["greedy"]),                  # gym: dropped
    ],
    "problemStatistics": [{"contestId": 1000, "index": "A", "solvedCount": 5000}],
}


def sub(i, cid, idx, t, verdict, ptype="PRACTICE"):
    return {"id": i, "contestId": cid, "creationTimeSeconds": t, "verdict": verdict,
            "programmingLanguage": "C++17",
            "problem": {"contestId": cid, "index": idx},
            "author": {"participantType": ptype, "members": [{"handle": "alice"}]}}


SUBMISSIONS = [
    sub(1, 1000, "A", T0, "COMPILATION_ERROR"),
    sub(2, 1000, "A", T0 + 60, "WRONG_ANSWER"),
    sub(3, 1000, "A", T0 + 120, "OK"),
    sub(4, 1000, "B", T0 + DAY, "OK", "CONTESTANT"),
    sub(5, 1000, "C", T0 + 2 * DAY, "WRONG_ANSWER", "CONTESTANT"),
    sub(6, 1000, "C", T0 + 4 * DAY, "OK"),                 # solved after the 24 h window
    sub(7, 1001, "A", T0 + 5 * DAY, "OK"),
    sub(8, 1001, "B", T0 + 6 * DAY, "TIME_LIMIT_EXCEEDED"),
    sub(9, 1002, "A", T0 + 7 * DAY, "OK"),
    sub(10, 1002, "B", T0 + 8 * DAY, "WRONG_ANSWER"),
    sub(11, 1002, "B", T0 + 8 * DAY + 3600, "OK"),
    sub(12, 1003, "A", T0 + 9 * DAY, "OK"),
    sub(13, 100500, "A", T0 + 9 * DAY, "OK"),              # gym: dropped
    sub(14, 1003, "B", T0 + 10 * DAY, "TESTING"),          # pending: ignored
]

RATING = [
    {"contestId": 1000, "contestName": "Round 1000", "rank": 900, "oldRating": 0, "newRating": 1100,
     "ratingUpdateTimeSeconds": T0 + DAY},
]


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    monkeypatch.setenv("UPSOLVE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("UPSOLVE_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("UPSOLVE_MODEL", str(tmp_path / "model.json"))
    import app.config
    importlib.reload(app.config)
    from app import cf_client, db, etl, model, coach
    for m in (db, etl, model, coach):
        importlib.reload(m)
    model.Predictor.reset()

    monkeypatch.setattr(cf_client, "problemset", lambda: json.loads(json.dumps(PROBLEMS)))
    monkeypatch.setattr(cf_client, "user_info", lambda handles: [{"handle": "alice", "rating": 1100, "rank": "newbie"}])
    monkeypatch.setattr(cf_client, "user_status", lambda handle, start=1, count=None: list(reversed(SUBMISSIONS)))
    monkeypatch.setattr(cf_client, "user_rating", lambda handle: RATING)
    return {"tmp": tmp_path}


@pytest.fixture()
def synced(app_env):
    from app import db, etl
    with db.session() as conn:
        etl.sync_user(conn, "alice")
    return app_env


@pytest.fixture()
def client(synced):
    import app.main
    importlib.reload(app.main)
    from fastapi.testclient import TestClient
    return TestClient(app.main.app)
