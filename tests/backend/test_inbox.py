"""Inbox / Digest endpoints (Tier 1).

List/action hit the real temp DB. retry-failed spins real background threads in
the service, so `ingest.retry`/`ingest.submit_youtube` are monkeypatched.
"""

from __future__ import annotations


def test_inbox_lists_pending_and_failed(client, make_item, make_task):
    make_item()
    make_item()
    make_task(status="failed", error="No subtitles", knowledge_item_id=None)

    data = client.get("/api/digest").json()
    assert len(data["pending"]) == 2
    assert len(data["failed"]) == 1
    assert data["counts"]["pending"] == 2
    assert data["counts"]["failed"] == 1
    assert data["counts"]["reviewed"] == 0
    # Pending items use the list shape (no transcript leaked).
    assert "raw_content" not in data["pending"][0]


def test_processing_count(client, make_item, make_task):
    make_item()
    make_task(status="processing")
    make_task(status="queued")
    counts = client.get("/api/digest").json()["counts"]
    assert counts["processing"] == 2


def test_action_keep_removes_from_pending(client, make_item):
    item_id = make_item()

    resp = client.post(f"/api/digest/{item_id}/action", json={"action": "keep"})
    assert resp.status_code == 200
    assert resp.json() == {"item_id": item_id, "action": "keep"}

    data = client.get("/api/digest").json()
    assert data["pending"] == []
    assert data["counts"]["pending"] == 0
    assert data["counts"]["reviewed"] == 1


def test_action_dismiss(client, make_item):
    item_id = make_item()
    resp = client.post(f"/api/digest/{item_id}/action", json={"action": "dismiss"})
    assert resp.status_code == 200
    assert client.get("/api/digest").json()["counts"]["reviewed"] == 1


def test_action_replaces_prior_decision(client, make_item):
    item_id = make_item()
    client.post(f"/api/digest/{item_id}/action", json={"action": "keep"})
    client.post(f"/api/digest/{item_id}/action", json={"action": "dismiss"})
    # One action per item — not two.
    assert client.get("/api/digest").json()["counts"]["reviewed"] == 1


def test_action_invalid_is_400(client, make_item):
    item_id = make_item()
    resp = client.post(f"/api/digest/{item_id}/action", json={"action": "frobnicate"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"


def test_action_unknown_item_is_404(client):
    resp = client.post("/api/digest/nope/action", json={"action": "keep"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_clear_failed(client, make_task):
    make_task(status="failed", error="boom")
    make_task(status="failed", error="boom2")
    make_task(status="completed")  # untouched

    resp = client.post("/api/digest/clear-failed")
    assert resp.status_code == 200
    assert resp.json() == {"cleared": 2}

    data = client.get("/api/digest").json()
    assert data["failed"] == []
    assert data["counts"]["failed"] == 0


def test_retry_failed_reenqueues_and_clears(client, make_item, make_task, monkeypatch):
    monkeypatch.setattr(
        "merlin.services.ingest.retry",
        lambda item_id, languages=None, summary_length=None: "rt-item",
    )
    monkeypatch.setattr(
        "merlin.services.ingest.submit_youtube",
        lambda url, languages, summary_length="short": "rt-url",
    )

    item_id = make_item()
    make_task(status="failed", knowledge_item_id=item_id, error="late failure")
    make_task(
        status="failed",
        knowledge_item_id=None,
        input_data={"raw_input": "https://youtu.be/x", "languages": ["en"]},
        error="early failure",
    )

    resp = client.post("/api/digest/retry-failed")
    assert resp.status_code == 200
    assert set(resp.json()["task_ids"]) == {"rt-item", "rt-url"}

    # Superseded failed rows are dropped after re-enqueue.
    assert client.get("/api/digest").json()["counts"]["failed"] == 0
