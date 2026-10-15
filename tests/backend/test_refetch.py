"""Re-fetch (fresh transcript + summary for an existing item) and the item
detail's provenance / ingest-usage fields.

The plugin's network work is skipped: `submit_ingest` is faked to run the
real `persist_result` callback inline with a canned IngestResult, so what's
asserted is the in-place update against the real temp DB.
"""

from __future__ import annotations

import json

import pytest

from merlin.knowledge_sources.base import IngestResult


def _result(video_id: str) -> IngestResult:
    return IngestResult(
        source_type="youtube",
        source_id=video_id,
        title="Le CRA en MONOCOMPTE sur DOFUS",
        author="HUZ REPLAY",
        raw_content="Comment faire sur Leveling Cra sur Dofus en 3.6 ?",
        summary="Un guide 1 à 200.",
        summary_length="short",
        tags=[],
        word_count=10,
        llm_model="deepseek/test",
        summarize_input_tokens=5000,
        summarize_output_tokens=800,
        summarize_cost_usd=0.002,
        source_metadata={
            "video_id": video_id,
            "channel": "HUZ REPLAY",
            "detected_language": "fr",
            "transcript_language": "fr",
            "transcript_source": "auto",
            "summary_language": "french",
            "timestamps": json.dumps({}),
        },
    )


@pytest.fixture
def inline_ingest(monkeypatch):
    """Run refetch's ingest synchronously: call on_complete with a fake result."""
    calls = {}

    def fake_submit(plugin, raw_input, options, on_complete):
        calls.update(raw_input=raw_input, options=options)
        video_id = raw_input.rsplit("=", 1)[-1]
        on_complete("task-refetch", _result(video_id))
        return "task-refetch"

    monkeypatch.setattr("merlin.services.ingest.task_queue.submit_ingest", fake_submit)
    monkeypatch.setattr("merlin.services.ingest._classify", lambda item_id: None)
    monkeypatch.setattr(
        "merlin.services.ingest._index_for_search", lambda item_id: None
    )
    return calls


def test_refetch_endpoint_returns_task_id(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "merlin.services.ingest.refetch",
        lambda item_id, languages=None, summary_length=None: captured.update(
            item_id=item_id, languages=languages
        )
        or "rf-1",
    )
    resp = client.post("/api/items/item-9/refetch", json={"languages": ["fr"]})
    assert resp.status_code == 200
    assert resp.json() == {"task_id": "rf-1"}
    assert captured == {"item_id": "item-9", "languages": ["fr"]}


def test_refetch_updates_in_place_and_keeps_user_state(
    client, make_item, make_task, inline_ingest
):
    from datetime import UTC, datetime

    item_id = make_item(
        source_id="zyJqVR7Svqo",
        raw_content="How do you level up a Cra on Dofus in 3.6?",
        tags=["dofus", "gaming"],
        saved_at=datetime(2026, 10, 1, tzinfo=UTC),
        read_at=datetime(2026, 10, 2, tzinfo=UTC),
    )
    make_task(id="task-refetch")

    resp = client.post(f"/api/items/{item_id}/refetch")
    assert resp.status_code == 200
    assert inline_ingest["raw_input"].endswith("v=zyJqVR7Svqo")
    # Summary languages don't inherit the (possibly wrong) stored language.
    assert inline_ingest["options"]["languages"] == ["en", "fr"]

    item = client.get(f"/api/items/{item_id}").json()
    assert item["id"] == item_id
    assert item["raw_content"].startswith("Comment faire")
    assert item["detected_language"] == "fr"
    assert item["transcript_language"] == "fr"
    assert item["transcript_source"] == "auto"
    assert item["summary_language"] == "french"
    assert item["tags"] == ["dofus", "gaming"]
    assert item["saved_at"] is not None
    assert item["read_at"] is not None
    assert item["ingest_usage"]["input_tokens"] == 5000
    assert item["ingest_usage"]["output_tokens"] == 800


def test_refetch_unknown_item_is_400(client):
    resp = client.post("/api/items/nope/refetch")
    assert resp.status_code == 400


def test_item_ingest_usage_latest_tokens_total_cost(client, make_item):
    from merlin.services import usage

    item_id = make_item()
    usage.record(
        surface="summarize",
        model="m",
        input_tokens=1000,
        output_tokens=100,
        cost_usd=0.01,
        knowledge_item_id=item_id,
    )
    usage.record(
        surface="summarize",
        model="m",
        input_tokens=2000,
        output_tokens=200,
        cost_usd=0.02,
        knowledge_item_id=item_id,
    )
    got = client.get(f"/api/items/{item_id}").json()["ingest_usage"]
    assert got["input_tokens"] == 2000
    assert got["output_tokens"] == 200
    assert got["cost_usd"] == pytest.approx(0.03)
    assert got["runs"] == 2


def test_item_without_usage_has_null_ingest_usage(client, make_item):
    item_id = make_item()
    item = client.get(f"/api/items/{item_id}").json()
    assert item["ingest_usage"] is None
    assert item["transcript_source"] is None
