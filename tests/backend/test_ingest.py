"""Ingest + task-inspection endpoints.

The submit/resummarize/retry handlers are pure glue over the service, and the
service spins up real background threads (network + LLM), so those service
calls are monkeypatched. Task list/get hit the real temp DB.
"""

from __future__ import annotations


def test_ingest_youtube_returns_task_id(client, monkeypatch):
    captured = {}

    def fake_submit(url, languages, summary_length="short"):
        captured.update(url=url, languages=languages, summary_length=summary_length)
        return {"status": "started", "task_id": "task-123"}

    monkeypatch.setattr("merlin.services.ingest.submit_youtube", fake_submit)

    resp = client.post(
        "/api/ingest/youtube",
        json={
            "url": "https://youtu.be/abc",
            "languages": ["en", "fr"],
            "summary_length": "long",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "started",
        "task_id": "task-123",
        "item_id": None,
        "title": None,
    }
    assert captured == {
        "url": "https://youtu.be/abc",
        "languages": ["en", "fr"],
        "summary_length": "long",
    }


def test_ingest_youtube_already_ingested_asks_to_confirm(client, monkeypatch):
    # An already-ingested URL is NOT re-summarised silently: the service reports
    # it exists so the client can confirm first.
    monkeypatch.setattr(
        "merlin.services.ingest.submit_youtube",
        lambda url, languages, summary_length="short": {
            "status": "exists",
            "item_id": "item-42",
            "title": "Already Here",
        },
    )
    resp = client.post("/api/ingest/youtube", json={"url": "https://youtu.be/dupe"})
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "exists",
        "task_id": None,
        "item_id": "item-42",
        "title": "Already Here",
    }


def test_ingest_youtube_defaults_languages(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "merlin.services.ingest.submit_youtube",
        lambda url, languages, summary_length="short": seen.update(
            languages=languages, summary_length=summary_length
        )
        or {"status": "started", "task_id": "t1"},
    )
    resp = client.post("/api/ingest/youtube", json={"url": "https://youtu.be/x"})
    assert resp.status_code == 200
    assert seen == {"languages": ["en", "fr"], "summary_length": "short"}


def test_ingest_youtube_bad_input_is_400(client, monkeypatch):
    def boom(*a, **k):
        raise ValueError("Invalid YouTube URL")

    monkeypatch.setattr("merlin.services.ingest.submit_youtube", boom)
    resp = client.post("/api/ingest/youtube", json={"url": "not-a-url"})
    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["code"] == "invalid_input"
    assert err["message"] == "Invalid YouTube URL"


def test_ingest_youtube_missing_url_is_422(client):
    resp = client.post("/api/ingest/youtube", json={})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_resummarize_returns_task_id(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "merlin.services.ingest.resummarize",
        lambda item_id, summary_length=None, languages=None: captured.update(
            item_id=item_id, summary_length=summary_length, languages=languages
        )
        or "rs-1",
    )
    resp = client.post("/api/items/item-9/resummarize", json={"summary_length": "long"})
    assert resp.status_code == 200
    assert resp.json() == {"task_id": "rs-1"}
    assert captured["item_id"] == "item-9"
    assert captured["summary_length"] == "long"


def test_resummarize_no_body(client, monkeypatch):
    monkeypatch.setattr(
        "merlin.services.ingest.resummarize",
        lambda *a, **k: "rs-2",
    )
    resp = client.post("/api/items/item-9/resummarize")
    assert resp.status_code == 200
    assert resp.json() == {"task_id": "rs-2"}


def test_retry_returns_task_id(client, monkeypatch):
    monkeypatch.setattr(
        "merlin.services.ingest.retry",
        lambda item_id, languages=None, summary_length=None: "retry-1",
    )
    resp = client.post("/api/items/item-7/retry")
    assert resp.status_code == 200
    assert resp.json() == {"task_id": "retry-1"}


def test_recent_tasks(client, make_task):
    make_task(status="completed", progress=100)
    rows = client.get("/api/tasks", params={"limit": 5}).json()
    assert len(rows) == 1
    assert rows[0]["status"] == "completed"
    assert rows[0]["progress"] == 100


def test_get_task(client, make_task):
    task_id = make_task(message="Downloading audio…")
    resp = client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 200
    task = resp.json()
    assert task["id"] == task_id
    assert task["message"] == "Downloading audio…"
    assert task["status"] == "processing"


def test_get_task_404(client):
    resp = client.get("/api/tasks/nope")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_cancel_task(client, make_task):
    task_id = make_task(status="processing")
    resp = client.post(f"/api/tasks/{task_id}/cancel")
    assert resp.status_code == 200
    assert resp.json() == {"task_id": task_id, "status": "cancelling"}


def test_cancel_unknown_task_404(client):
    resp = client.post("/api/tasks/nope/cancel")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_cancel_finished_task_404(client, make_task):
    # A terminal task has nothing to cancel.
    task_id = make_task(status="completed", progress=100)
    resp = client.post(f"/api/tasks/{task_id}/cancel")
    assert resp.status_code == 404
