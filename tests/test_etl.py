from conftest import PROBLEMS, SUBMISSIONS, DAY, T0


def test_transform_problems_drops_gym_and_special_tags():
    from app.etl import transform_problems
    rows = {r["problem_id"]: r for r in transform_problems(PROBLEMS)}
    assert "100500A" not in rows
    assert rows["1003B"]["tags"] == ["graphs"]          # '*special' removed
    assert rows["1000A"]["solved_count"] == 5000
    assert rows["1004D"]["rating"] is None


def test_dedup_key_matches_reused_statements():
    from app.etl import transform_problems
    raw = {"problems": [
        {"contestId": 1, "index": "C", "name": "Same  Name", "type": "PROGRAMMING", "rating": 1500, "tags": []},
        {"contestId": 2, "index": "A", "name": "same name", "type": "PROGRAMMING", "rating": 1500, "tags": []},
    ]}
    a, b = transform_problems(raw)
    assert a["dedup_key"] == b["dedup_key"]


def test_build_attempts_rules():
    from app.etl import transform_submissions, build_attempts
    attempts = {a["problem_id"]: a for a in build_attempts(transform_submissions(SUBMISSIONS, "alice"))}
    # compilation error ignored: attempt starts at the wrong answer, solved within 24 h
    assert attempts["1000A"]["first_at"] == T0 + 60
    assert attempts["1000A"]["solved"] == 1
    assert attempts["1000A"]["n_submissions"] == 2
    # accepted after the 24 h window: not solved for the label, but ever solved
    assert attempts["1000C"]["solved"] == 0 and attempts["1000C"]["ever_solved"] == 1
    assert attempts["1000C"]["in_contest"] == 1
    # failure only
    assert attempts["1001B"]["solved"] == 0 and attempts["1001B"]["ever_solved"] == 0
    # pending judgement alone creates no attempt; gym problems are dropped
    assert "1003B" not in attempts
    assert "100500A" not in attempts


def test_transform_submissions_dedups_ids():
    from app.etl import transform_submissions
    rows = transform_submissions(SUBMISSIONS + SUBMISSIONS[:3], "alice")
    assert len(rows) == len({r["id"] for r in rows})


def test_sync_is_incremental(synced):
    from app import db, etl, cf_client
    calls = []

    def fake_status(handle, start=1, count=None):
        calls.append((start, count))
        new = {"id": 99, "contestId": 1003, "creationTimeSeconds": T0 + 20 * DAY, "verdict": "OK",
               "problem": {"contestId": 1003, "index": "C"}, "author": {"participantType": "PRACTICE"}}
        return [new] + list(reversed(SUBMISSIONS))

    cf_client.user_status = fake_status
    with db.session() as conn:
        summary = etl.sync_user(conn, "alice")
        # only the new submission plus the still-pending one (id 14) are loaded again
        assert summary["new_submissions"] == 2
        assert calls[0][1] == 500                      # paged, not a full re-download
        n = conn.execute("SELECT COUNT(*) FROM submissions WHERE handle='alice'").fetchone()[0]
        assert n == 14                                  # 13 regular + 1 new, no duplicates
