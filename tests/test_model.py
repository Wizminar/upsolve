import numpy as np


def test_expected_is_symmetric():
    from app.elo import expected
    assert abs(expected(1500, 1500) - 0.5) < 1e-9
    assert abs(expected(1500, 1900) + expected(1900, 1500) - 1) < 1e-9
    assert expected(1900, 1500) > 0.9


def test_solving_raises_and_failing_lowers_ratings():
    from app.elo import PracticeState
    up, down = PracticeState(), PracticeState()
    for _ in range(5):
        up.update(1500, ["dp"], 1, 0)
        down.update(1500, ["dp"], 0, 0)
    assert up.overall > down.overall
    assert up.tag("dp")["n"] == 5


def test_topic_offsets_are_relative():
    from app.elo import PracticeState
    st = PracticeState()
    for i in range(30):
        st.update(1400, ["greedy"], 1, i)
        st.update(1400, ["graphs"], 0, i)
    assert st.tag("greedy")["r"] > st.overall > st.tag("graphs")["r"]
    total = sum(t["n"] for t in st.tags.values())
    assert abs(sum(t["n"] * t["d"] for t in st.tags.values()) / total) < 1e-6


def test_contest_anchor_limits_drift():
    from app.elo import ContestTimeline, PracticeState
    st = PracticeState(ContestTimeline([(0, 1400)]))
    st.set_time(1)
    for i in range(500):
        st.update(1400, ["math"], 1, i)        # solving everything at one's own level
    assert st.overall < 1400 + 250, "form offset should decay instead of running away"


def test_features_use_only_past(synced):
    from app import db, elo
    with db.session() as conn:
        rows = elo.load_attempt_rows(conn, "alice")
        seen = []
        elo.replay(rows, elo.load_timeline(conn, "alice"), on_attempt=lambda s, r: seen.append(s.n))
    assert seen == list(range(len(rows)))       # each snapshot sees exactly the earlier attempts


def test_metrics():
    from app.model import _auc, evaluate
    y = np.array([0, 0, 1, 1])
    assert _auc(y, np.array([0.1, 0.2, 0.8, 0.9])) == 1.0
    assert _auc(y, np.array([0.9, 0.8, 0.2, 0.1])) == 0.0
    m = evaluate(y, np.array([0.1, 0.6, 0.65, 0.9]))
    assert m["target_band"]["n"] == 2 and m["n"] == 4
    assert sum(b["count"] for b in m["calibration"]) == 4


def test_predictor_falls_back_to_elo(app_env):
    from app.model import Predictor
    p = Predictor.get()
    assert p.source == "elo"
    probs = p.predict_many([[0.0] + [0] * 10, [2.0] + [0] * 10])
    assert abs(probs[0] - 0.5) < 1e-9 and probs[1] > 0.8


def test_train_writes_artifact(synced, monkeypatch):
    from app import db, model, config
    # Re-use alice's attempts many times so there is enough data to fit.
    X = np.random.default_rng(0).normal(size=(400, 11))
    y = (X[:, 0] + np.random.default_rng(1).normal(size=400) > 0).astype(int)
    ts = np.arange(400)
    monkeypatch.setattr(model, "build_training_set", lambda conn: (X, y, ts, np.zeros(400)))
    with db.session() as conn:
        art = model.train(conn)
    assert config.MODEL_PATH.exists()
    assert art["split"]["train_attempts"] == 320 and art["split"]["test_attempts"] == 80
    assert art["metrics"]["model"]["auc"] > 0.6
    assert model.Predictor.get().source == "model"


def test_implicit_contest_failures(synced):
    from app import db, elo
    with db.session() as conn:
        rows = elo.load_attempt_rows(conn, "alice")
    implicit = {r["problem_id"]: r for r in rows if r["implicit"]}
    assert "1000D" in implicit                       # in the rated round, never attempted
    assert implicit["1000D"]["solved"] == 0 and implicit["1000D"]["in_contest"] == 1
    assert "1000A" not in implicit                   # solved before the round started
    assert "1000B" not in implicit                   # attempted during the round
    assert all(r["first_at"] <= rows[i + 1]["first_at"] for i, r in enumerate(rows[:-1]))


def test_implicit_games_do_not_count_as_attempts(synced):
    from app import db, elo
    with db.session() as conn:
        st = elo.state_for(conn, "alice")
    assert st.a == 8 and st.n > st.a
