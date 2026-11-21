def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_unsynced_handle_returns_helpful_404(client):
    r = client.get("/api/v1/users/bob_unknown/profile")
    assert r.status_code == 404
    assert "POST /api/v1/users/bob_unknown/sync" in r.json()["detail"]


def test_invalid_handle_rejected(client):
    assert client.get("/api/v1/users/a/profile").status_code == 422


def test_profile_and_insights(client):
    p = client.get("/api/v1/users/alice/profile").json()
    assert p["handle"] == "alice" and p["attempts"] == 8 and p["problems_solved"] == 7
    topics = client.get("/api/v1/users/alice/topics").json()
    assert {t["tag"] for t in topics} >= {"dp", "greedy", "implementation"}
    assert all(t["confidence"] in ("low", "medium", "high") for t in topics)
    assert client.get("/api/v1/users/alice/topics/dp/history").status_code == 200
    assert len(client.get("/api/v1/users/alice/rating-history").json()) == 1
    assert client.get("/api/v1/users/alice/activity?days=730").status_code == 200


def test_recommendations_exclude_solved(client):
    r = client.get("/api/v1/users/alice/recommendations?count=3").json()
    solved = {"1000A", "1000B", "1000C", "1001A", "1002A", "1002B", "1003A"}
    assert r["items"], "expected at least one recommendation"
    for item in r["items"]:
        assert item["problem_id"] not in solved
        assert 0 < item["probability"] < 1
        assert item["reasons"][0]["kind"] == "probability"
        assert item["url"].startswith("https://codeforces.com/problemset/problem/")
    # 1001B was failed earlier, so if it is recommended it must be flagged as an upsolve
    for item in r["items"]:
        if item["problem_id"] == "1001B":
            assert item["upsolve"]


def test_recommendations_are_stable_per_refresh(client):
    a = client.get("/api/v1/users/alice/recommendations?count=3").json()["items"]
    b = client.get("/api/v1/users/alice/recommendations?count=3").json()["items"]
    assert [x["problem_id"] for x in a] == [x["problem_id"] for x in b]


def test_training_settings_validation(client):
    ok = client.put("/api/v1/users/alice/training", json={"topics": ["dp", "graphs"], "weekly_target": 4})
    assert ok.status_code == 200 and ok.json()["topics"] == ["dp", "graphs"]
    assert client.put("/api/v1/users/alice/training", json={"topics": ["dp", "graphs", "math"]}).status_code == 422
    assert client.put("/api/v1/users/alice/training", json={"topics": ["not-a-tag"]}).status_code == 422
    assert client.put("/api/v1/users/alice/training", json={"topics": [], "weekly_target": 0}).status_code == 422


def test_plan(client):
    client.put("/api/v1/users/alice/training", json={"topics": ["dp"], "weekly_target": 3})
    plan = client.get("/api/v1/users/alice/plan").json()
    assert plan["weekly_target"] == 3 and len(plan["days"]) == 7
    assert sum(len(d["planned"]) for d in plan["days"]) == 3


def test_predict(client):
    r = client.get("/api/v1/users/alice/predict/1002C")
    assert r.status_code == 200 and 0 < r.json()["probability"] < 1
    assert client.get("/api/v1/users/alice/predict/9999Z").status_code == 404
    assert client.get("/api/v1/users/alice/predict/1004D").status_code == 422   # unrated


def test_feedback_counts_shown(client):
    client.get("/api/v1/users/alice/recommendations?count=2")
    fb = client.get("/api/v1/users/alice/feedback").json()
    assert fb["shown"] >= 1


def test_plugin_registry_and_store(client):
    plugins = client.get("/api/v1/plugins").json()
    rival = next(p for p in plugins if p["id"] == "rival")
    assert rival["valid"] and rival["enabled"]
    base = "/api/v1/plugins/rival/store/alice"
    assert client.get(f"{base}/missing").status_code == 404
    assert client.put(f"{base}/rival", json={"value": {"handle": "bob"}}).status_code == 200
    assert client.get(f"{base}/rival").json()["value"] == {"handle": "bob"}
    assert client.get(base).json() == {"rival": {"handle": "bob"}}
    assert client.delete(f"{base}/rival").status_code == 204
    assert client.get("/api/v1/plugins/nope/store/alice").status_code == 404
    off = client.put("/api/v1/plugins/rival", json={"enabled": False}).json()
    assert off["enabled"] is False
    client.put("/api/v1/plugins/rival", json={"enabled": True})


def test_openapi_lists_core_endpoints(client):
    paths = client.get("/api/v1/openapi.json").json()["paths"]
    for p in ["/api/v1/users/{handle}/sync", "/api/v1/users/{handle}/recommendations",
              "/api/v1/users/{handle}/training", "/api/v1/plugins/{plugin_id}/store/{scope}/{key}"]:
        assert p in paths


def test_text_view(client):
    r = client.get("/text/alice")
    assert r.status_code == 200 and "<table" in r.text and "<script" not in r.text
