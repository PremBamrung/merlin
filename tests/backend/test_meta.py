"""Meta: health, OpenAPI schema, and the universal error envelope."""

from __future__ import annotations


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "youtube" in body["source_types"]


def test_openapi_exposes_every_tier0_endpoint(client):
    paths = client.get("/openapi.json").json()["paths"]
    expected = {
        "/api/items",
        "/api/items/{item_id}",
        "/api/items/{item_id}/clear-summary",
        "/api/items/{item_id}/resummarize",
        "/api/items/{item_id}/retry",
        "/api/ingest/youtube",
        "/api/tasks",
        "/api/tasks/{task_id}",
        "/api/tasks/{task_id}/stream",
        "/api/chat",
        "/api/tags",
        "/api/source-types",
        "/api/insights/timeline",
        "/api/insights/top-channels",
        "/api/insights/status-counts",
        "/api/insights/channel-count",
    }
    assert expected.issubset(set(paths))


def test_unknown_route_uses_error_envelope(client):
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert set(body["error"].keys()) == {"code", "message", "detail"}
    assert body["error"]["code"] == "not_found"


def test_insights_endpoints(client, make_item):
    make_item(channel="Andrej Karpathy")
    make_item(source_id="v2", channel="Andrej Karpathy")
    make_item(source_id="v3", channel="Other")

    assert client.get("/api/insights/channel-count").json() == {"count": 2}

    status = {
        r["name"]: r["count"] for r in client.get("/api/insights/status-counts").json()
    }
    assert status["completed"] == 3

    channels = {
        r["name"]: r["count"] for r in client.get("/api/insights/top-channels").json()
    }
    assert channels["Andrej Karpathy"] == 2

    timeline = client.get("/api/insights/timeline").json()
    assert sum(p["count"] for p in timeline) == 3
