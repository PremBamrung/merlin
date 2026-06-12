"""Task-progress SSE endpoint — progress* → terminal, by polling get_task."""

from __future__ import annotations

import json


def _frames(text: str) -> list[dict]:
    out = []
    for block in text.strip().split("\n\n"):
        block = block.strip()
        if block.startswith("data:"):
            out.append(json.loads(block[len("data:") :].strip()))
    return out


def _task(**kw):
    base = {
        "id": "t1",
        "task_type": "ingest_youtube",
        "status": "processing",
        "progress": 10,
        "message": "Starting…",
        "error": None,
        "knowledge_item_id": None,
        "created_at": None,
        "result_data": None,
    }
    base.update(kw)
    return base


def test_stream_progress_then_complete(client, monkeypatch):
    # No real sleeping between polls.
    monkeypatch.setattr("api.sse.TASK_STREAM_POLL_INTERVAL", 0)

    states = iter(
        [
            _task(status="processing", progress=10),  # pre-check
            _task(status="processing", progress=10),  # poll 1 → progress
            _task(status="processing", progress=60, message="Half"),  # poll 2
            _task(
                status="completed",
                progress=100,
                knowledge_item_id="item-9",
            ),  # poll 3 → complete
        ]
    )
    completed = _task(status="completed", progress=100, knowledge_item_id="item-9")
    monkeypatch.setattr(
        "merlin.services.ingest.get_task",
        lambda task_id: next(states, completed),
    )

    frames = _frames(client.get("/api/tasks/t1/stream").text)
    types = [f["type"] for f in frames]
    assert types[-1] == "complete"
    assert "progress" in types
    assert frames[-1]["task"]["knowledge_item_id"] == "item-9"
    # Progress only emitted when the signature changes (10 then 60 → 2 ticks).
    progress_frames = [f for f in frames if f["type"] == "progress"]
    assert [f["task"]["progress"] for f in progress_frames] == [10, 60]


def test_stream_failed(client, monkeypatch):
    monkeypatch.setattr("api.sse.TASK_STREAM_POLL_INTERVAL", 0)
    states = iter(
        [
            _task(status="processing"),  # pre-check
            _task(status="failed", error="yt-dlp: video unavailable"),  # poll 1
        ]
    )
    fail = _task(status="failed", error="yt-dlp: video unavailable")
    monkeypatch.setattr(
        "merlin.services.ingest.get_task",
        lambda task_id: next(states, fail),
    )

    frames = _frames(client.get("/api/tasks/t1/stream").text)
    assert frames[-1]["type"] == "failed"
    assert frames[-1]["task"]["error"] == "yt-dlp: video unavailable"


def test_stream_unknown_task_emits_error(client, monkeypatch):
    monkeypatch.setattr("api.sse.TASK_STREAM_POLL_INTERVAL", 0)
    monkeypatch.setattr("merlin.services.ingest.get_task", lambda task_id: None)

    frames = _frames(client.get("/api/tasks/nope/stream").text)
    assert frames == [
        {
            "type": "error",
            "error": {
                "code": "not_found",
                "message": "Task not found.",
                "detail": None,
            },
        }
    ]
