"""LLM usage / cost tracking — pricing math, the usage service, and the chat +
ingest capture seams. Visibility only: nothing here asserts any throttling.

Cost is provider-reported in prod; tests run with no network (FunctionModel has
no generation id → the OpenRouter cost lookup short-circuits to None), so they
assert the rows + token counts land, and pricing math separately.
"""

from __future__ import annotations

import json

import pytest

from merlin import llm_pricing

# --------------------------------------------------------------------------- #
# Pricing map (fallback cost source)
# --------------------------------------------------------------------------- #


def test_token_cost_known_model():
    # 1M in + 1M out at the deepseek rate (no cache hits → full input rate).
    c = llm_pricing.cost(
        "openrouter",
        "deepseek/deepseek-v4-flash",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    rates = llm_pricing.TOKEN_PRICING["deepseek/deepseek-v4-flash"]
    assert c == pytest.approx(rates["in"] + rates["out"])


def test_token_cost_prices_cache_hits_cheaper():
    """Cached input is billed at the discounted `cache_read` rate, not `in` —
    so a turn whose prompt is mostly a cache hit costs far less than the naive
    (all-input-at-full-rate) number."""
    rates = llm_pricing.TOKEN_PRICING["deepseek/deepseek-v4-flash"]
    # 1M prompt, 900k of it a cache hit, no output.
    c = llm_pricing.cost(
        "openrouter",
        "deepseek/deepseek-v4-flash",
        input_tokens=1_000_000,
        output_tokens=0,
        cache_read_tokens=900_000,
    )
    expected = 0.1 * rates["in"] + 0.9 * rates["cache_read"]
    assert c == pytest.approx(expected)
    # Strictly cheaper than pricing the whole prompt at the full input rate.
    assert c < rates["in"]


def test_token_cost_resolves_versioned_model_name():
    """The response reports a resolved/versioned id; it prices off the base key
    (our configured `@preset/…` is what would otherwise miss)."""
    c = llm_pricing.cost(
        "openrouter",
        "deepseek/deepseek-v4-flash-20260423",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    assert c == pytest.approx(
        llm_pricing.TOKEN_PRICING["deepseek/deepseek-v4-flash"]["in"]
    )


def test_token_cost_unknown_model_is_none():
    # Unknown / preset models can't be priced → None (Insights shows "unknown").
    assert llm_pricing.cost("openrouter", "@preset/whatever", input_tokens=1000) is None


def test_audio_cost_uses_per_hour_rate():
    c = llm_pricing.cost("groq", "whisper-large-v3-turbo", audio_seconds=3600)
    assert c == llm_pricing.AUDIO_PRICING_PER_HOUR["whisper-large-v3-turbo"]


def test_cost_none_when_nothing_to_price():
    assert llm_pricing.cost("azure", None) is None


# --------------------------------------------------------------------------- #
# Usage service — record + aggregates
# --------------------------------------------------------------------------- #


def _rows():
    from merlin.db.engine import SessionFactory
    from merlin.db.models import LlmUsage

    with SessionFactory() as s:
        return s.query(LlmUsage).all()


def test_record_writes_row_and_computes_cost(client):
    from merlin.services import usage

    usage.record(
        surface="summarize",
        provider="openrouter",
        model="deepseek/deepseek-v4-flash",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    rows = _rows()
    assert len(rows) == 1
    row = rows[0]
    assert row.surface == "summarize"
    # Cost computed from the map when not supplied.
    assert row.cost_usd == llm_pricing.TOKEN_PRICING["deepseek/deepseek-v4-flash"]["in"]


def test_record_prefers_explicit_cost(client):
    from merlin.services import usage

    usage.record(
        surface="chat",
        provider="openrouter",
        model="@preset/x",
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.0042,  # provider-reported wins over the (absent) map entry
    )
    assert _rows()[0].cost_usd == 0.0042


def test_aggregates_sum(client):
    from merlin.services import usage

    usage.record(
        surface="chat", model="m", input_tokens=10, output_tokens=2, cost_usd=1.0
    )
    usage.record(
        surface="chat", model="m", input_tokens=5, output_tokens=1, cost_usd=2.0
    )
    usage.record(surface="summarize", model="m", input_tokens=3, cost_usd=0.5)

    total = usage.total_spend()
    assert total["calls"] == 3
    assert total["cost_usd"] == 3.5
    assert total["tokens_in"] == 18

    by_surface = {r["surface"]: r for r in usage.spend_by_surface()}
    assert by_surface["chat"]["calls"] == 2
    assert by_surface["chat"]["cost_usd"] == 3.0


def test_cost_for_item(client, make_item):
    from merlin.services import usage

    item_id = make_item(title="x")
    usage.record(
        surface="summarize", model="m", cost_usd=0.01, knowledge_item_id=item_id
    )
    usage.record(
        surface="transcribe", model="w", cost_usd=0.02, knowledge_item_id=item_id
    )

    assert usage.cost_for_item(item_id) == 0.03
    assert usage.cost_for_item("no-such-item") is None  # unknown ≠ $0


# --------------------------------------------------------------------------- #
# Ingest capture — persist_result writes summarize (+ transcribe) rows
# --------------------------------------------------------------------------- #


def test_record_ingest_usage_writes_rows(client, make_item):
    from merlin.knowledge_sources.base import IngestResult
    from merlin.services import ingest

    item_id = make_item(title="ingested")
    result = IngestResult(
        source_type="youtube",
        source_id="vid1",
        title="ingested",
        llm_model="deepseek/deepseek-v4-flash",
        summarize_input_tokens=100,
        summarize_output_tokens=50,
        summarize_cost_usd=0.001,
        transcribe_audio_seconds=120.0,
        transcribe_model="whisper-large-v3-turbo",
    )
    ingest._record_ingest_usage(item_id, result)

    rows = {r.surface: r for r in _rows()}
    assert set(rows) == {"summarize", "transcribe"}
    assert rows["summarize"].cost_usd == 0.001  # provider-reported preferred
    assert rows["summarize"].knowledge_item_id == item_id
    # Transcribe has no passthrough → cost computed from audio seconds.
    assert rows["transcribe"].audio_seconds == 120.0
    assert rows["transcribe"].cost_usd is not None


def test_record_ingest_usage_skips_when_no_summary_usage(client, make_item):
    from merlin.knowledge_sources.base import IngestResult
    from merlin.services import ingest

    item_id = make_item(title="no-usage")
    # All usage fields None (older item / provider without passthrough) → no rows.
    result = IngestResult(source_type="youtube", source_id="v", title="no-usage")
    ingest._record_ingest_usage(item_id, result)
    assert _rows() == []


# --------------------------------------------------------------------------- #
# Chat capture — a finished turn records one chat row (via background task)
# --------------------------------------------------------------------------- #


def _chat_body(text: str, filters: dict | None = None) -> dict:
    body = {
        "id": "conv-1",
        "trigger": "submit-message",
        "messages": [
            {"id": "m1", "role": "user", "parts": [{"type": "text", "text": text}]}
        ],
    }
    if filters is not None:
        body["filters"] = filters
    return body


def _text_model(answer: str):
    from pydantic_ai.models.function import FunctionModel

    async def stream_fn(messages, info):
        yield answer

    return FunctionModel(stream_function=stream_fn)


def test_chat_turn_records_usage_row(client, monkeypatch, make_item):
    """A completed /api/chat turn writes one surface='chat' llm_usage row.

    No generation id (FunctionModel) → the OpenRouter cost lookup short-circuits,
    so cost is NULL but the row + token counts + requests still land. The
    TestClient runs the FastAPI background task synchronously after the response.
    """
    make_item(title="A video about moats", summary="moats and edges")
    monkeypatch.setattr(
        "merlin.services.chat.build_chat_model",
        lambda: _text_model("Your library covers moats."),
        raising=True,
    )

    resp = client.post("/api/chat", json=_chat_body("what about moats?"))
    assert resp.status_code == 200

    chat_rows = [r for r in _rows() if r.surface == "chat"]
    assert len(chat_rows) == 1
    row = chat_rows[0]
    assert row.provider == "openrouter"
    assert (row.requests or 0) >= 1
    # meta is JSON (cache/tool_calls); no generation id was available offline.
    assert row.meta is None or "generation_id" not in json.loads(row.meta)
