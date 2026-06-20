"""Agentic chat endpoint — drives the real router → VercelAIAdapter → agent →
tools → SQLite path, with the model scripted by Pydantic AI's FunctionModel /
TestModel so there is **no network**.

The wire format is the Vercel AI SDK v6 data-stream protocol (SSE), so we assert
on the `type` of each emitted part rather than the old citations/tokens/done
frames.
"""

from __future__ import annotations

import json

import pytest

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _sse_types(text: str) -> list[str]:
    """All `type` discriminators emitted in the SSE body, in order."""
    types = []
    for block in text.strip().split("\n\n"):
        block = block.strip()
        if block.startswith("data:"):
            payload = block[len("data:") :].strip()
            if payload and payload != "[DONE]":
                try:
                    types.append(json.loads(payload).get("type"))
                except json.JSONDecodeError:
                    pass
    return types


def _sse_objects(text: str) -> list[dict]:
    out = []
    for block in text.strip().split("\n\n"):
        block = block.strip()
        if block.startswith("data:"):
            payload = block[len("data:") :].strip()
            if payload and payload != "[DONE]":
                try:
                    out.append(json.loads(payload))
                except json.JSONDecodeError:
                    pass
    return out


def _data_part(text: str, part_type: str) -> list[dict]:
    """The `data.items` of the first data-part of `part_type` (or [])."""
    for obj in _sse_objects(text):
        if obj.get("type") == part_type:
            return obj.get("data", {}).get("items", [])
    return []


def _ids(items: list[dict]) -> set[str]:
    return {i["item_id"] for i in items}


def _chat_body(text: str, filters: dict | None = None) -> dict:
    """A minimal AI SDK v6 sendMessage body (+ our extra filters field)."""
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


def _has_tool_return(messages) -> bool:
    return any(
        getattr(p, "part_kind", "") == "tool-return"
        for m in messages
        for p in getattr(m, "parts", [])
    )


def _search_then_answer_model(query: str, answer: str, captured: dict | None = None):
    """A streaming model: first turn calls search_library(query), then answers.

    The adapter drives *streamed* requests, so FunctionModel needs a
    `stream_function` (an async generator yielding text deltas or
    `DeltaToolCalls`).
    """
    from pydantic_ai.models.function import DeltaToolCall, FunctionModel

    async def stream_fn(messages, info):
        if captured is not None:
            captured["tool_count"] = len(info.function_tools)
        if _has_tool_return(messages):
            yield answer
        else:
            yield {
                0: DeltaToolCall(
                    name="search_library",
                    json_args=json.dumps({"query": query}),
                    tool_call_id="call-1",
                )
            }

    return FunctionModel(stream_function=stream_fn)


def _loop_model(query: str):
    """A streaming model that *never* finalises — always calls the tool."""
    from pydantic_ai.models.function import DeltaToolCall, FunctionModel

    async def stream_fn(messages, info):
        yield {
            0: DeltaToolCall(
                name="search_library",
                json_args=json.dumps({"query": query}),
                tool_call_id="call-x",
            )
        }

    return FunctionModel(stream_function=stream_fn)


def _text_model(answer: str, captured: dict | None = None):
    """A streaming model that just emits text (no tools)."""
    from pydantic_ai.models.function import FunctionModel

    async def stream_fn(messages, info):
        if captured is not None:
            captured["tool_count"] = len(info.function_tools)
        yield answer

    return FunctionModel(stream_function=stream_fn)


def _patch_model(monkeypatch, model):
    """Make the route build `model` instead of the real OpenRouter client."""
    monkeypatch.setattr(
        "merlin.services.chat.build_chat_model", lambda: model, raising=True
    )


# --------------------------------------------------------------------------- #
# Library-wide agentic chat
# --------------------------------------------------------------------------- #


def test_library_chat_streams_tool_then_text(client, monkeypatch, make_item):
    """A scripted search → answer run emits tool-call + tool-result + text +
    the consolidated citations data-part, and accumulates real DB citations."""
    make_item(title="A video about moats", summary="Discussion of moats and edges.")

    _patch_model(
        monkeypatch,
        _search_then_answer_model("moats", "Your library covers moats."),
    )

    resp = client.post("/api/chat", json=_chat_body("what about moats?"))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    # No-buffer header is set so proxies don't swallow the stream.
    assert resp.headers.get("x-accel-buffering") == "no"

    types = _sse_types(resp.text)
    # The agent's tool call + result and the final text all surface as parts.
    assert "tool-input-available" in types
    assert "tool-output-available" in types
    assert "text-delta" in types
    assert "finish" in types

    # Consolidated citations data-part carries the real item we inserted.
    cites = [o for o in _sse_objects(resp.text) if o.get("type") == "data-citations"]
    assert cites, "expected a data-citations part"
    titles = [c["title"] for c in cites[0]["data"]["items"]]
    assert any("moats" in t.lower() for t in titles)


def test_library_chat_passes_filters_into_search(client, monkeypatch, make_item):
    """FilterBar source_types flow through ChatDeps into the retriever."""
    make_item(title="YT moat", source_type="youtube", summary="moat")
    make_item(title="RD moat", source_type="reddit", source_id="r1", summary="moat")

    # No explicit source_types arg → the tool should inherit the chat filter.
    _patch_model(monkeypatch, _search_then_answer_model("moat", "done"))

    resp = client.post(
        "/api/chat",
        json=_chat_body("moat?", filters={"source_types": ["youtube"]}),
    )
    cites = [o for o in _sse_objects(resp.text) if o.get("type") == "data-citations"]
    assert cites
    sources = {c["source_type"] for c in cites[0]["data"]["items"]}
    assert sources == {"youtube"}  # reddit item filtered out by the chat filter


def test_request_limit_is_enforced(client, monkeypatch, make_item):
    """A model that never stops calling tools is capped by chat_max_requests."""
    make_item(title="loopy", summary="moat")
    monkeypatch.setattr("merlin.config.settings.chat_max_requests", 2)

    _patch_model(monkeypatch, _loop_model("moat"))

    resp = client.post("/api/chat", json=_chat_body("loop forever"))
    # The stream still terminates (the adapter surfaces the limit) rather than
    # running away; an error part is emitted.
    types = _sse_types(resp.text)
    assert "error" in types or "finish" in types
    assert types  # something was streamed, the request didn't hang


# --------------------------------------------------------------------------- #
# Used-vs-viewed citation split (inline [#id] markers)
# --------------------------------------------------------------------------- #

# Marker-regex-shaped ids (UUIDs), so the model's `[#id]` markers parse.
_ID1 = "11111111-1111-1111-1111-111111111111"
_ID2 = "22222222-2222-2222-2222-222222222222"
_ID3 = "33333333-3333-3333-3333-333333333333"


def _three_moat_items(make_item):
    """Three retrievable items sharing the keyword 'moat', with known ids."""
    make_item(id=_ID1, title="Alpha edge", source_id="a1", summary="moat one")
    make_item(id=_ID2, title="Beta castle", source_id="b2", summary="moat two")
    make_item(id=_ID3, title="Gamma wall", source_id="c3", summary="moat three")


def test_markers_split_used_vs_viewed(client, monkeypatch, make_item):
    """An answer tagging one item with `[#id]` cites only that item; the rest
    fall to the 'Also searched' (data-sources-viewed) tier."""
    _three_moat_items(make_item)
    _patch_model(
        monkeypatch,
        _search_then_answer_model("moat", f"Moats matter [#{_ID1}]."),
    )

    resp = client.post("/api/chat", json=_chat_body("tell me about moats"))
    assert resp.status_code == 200

    used = _data_part(resp.text, "data-citations")
    viewed = _data_part(resp.text, "data-sources-viewed")
    assert _ids(used) == {_ID1}
    assert _ids(viewed) == {_ID2, _ID3}


def test_abbreviated_marker_id_resolves_by_prefix(client, monkeypatch, make_item):
    """Models often shorten UUIDs (`[#11111111]` for `1111…`); a unique prefix
    still resolves to the right item."""
    _three_moat_items(make_item)
    _patch_model(
        monkeypatch,
        _search_then_answer_model("moat", "Moats matter [#11111111]."),
    )

    resp = client.post("/api/chat", json=_chat_body("moats?"))
    used = _data_part(resp.text, "data-citations")
    assert _ids(used) == {_ID1}
    assert _ids(_data_part(resp.text, "data-sources-viewed")) == {_ID2, _ID3}


def test_marker_without_hash_is_matched(client, monkeypatch, make_item):
    """Models frequently drop the `#`, mirroring the `[id]` shown in tool output;
    the bare `[id]` form still resolves."""
    _three_moat_items(make_item)
    _patch_model(
        monkeypatch,
        _search_then_answer_model("moat", "Moats matter [11111111]."),
    )

    resp = client.post("/api/chat", json=_chat_body("moats?"))
    used = _data_part(resp.text, "data-citations")
    assert _ids(used) == {_ID1}
    assert _ids(_data_part(resp.text, "data-sources-viewed")) == {_ID2, _ID3}


def test_no_markers_falls_back_to_title_match(client, monkeypatch, make_item):
    """No markers → an item whose title appears verbatim is treated as used."""
    _three_moat_items(make_item)
    _patch_model(
        monkeypatch,
        _search_then_answer_model("moat", "The Beta castle had the widest moat."),
    )

    resp = client.post("/api/chat", json=_chat_body("which had the widest moat?"))
    used = _data_part(resp.text, "data-citations")
    assert _ID2 in _ids(used)


def test_no_markers_no_title_match_cites_all_viewed(client, monkeypatch, make_item):
    """A generic answer with neither markers nor title hits cites every viewed
    item — the Sources list is never empty when the library was clearly used."""
    _three_moat_items(make_item)
    _patch_model(
        monkeypatch,
        _search_then_answer_model("moat", "Defensibility comes from many factors."),
    )

    resp = client.post("/api/chat", json=_chat_body("what makes a business strong?"))
    used = _data_part(resp.text, "data-citations")
    assert _ids(used) == {_ID1, _ID2, _ID3}
    assert _data_part(resp.text, "data-sources-viewed") == []


def test_hallucinated_marker_id_is_dropped(client, monkeypatch, make_item):
    """A marker for an id no tool surfaced is ignored; only real cited ids win."""
    _three_moat_items(make_item)
    _patch_model(
        monkeypatch,
        _search_then_answer_model(
            "moat", f"Real [#{_ID1}] and fake [#deadbeefcafe]."
        ),
    )

    resp = client.post("/api/chat", json=_chat_body("moats?"))
    used = _data_part(resp.text, "data-citations")
    assert _ids(used) == {_ID1}  # deadbeefcafe never appears
    assert _ids(_data_part(resp.text, "data-sources-viewed")) == {_ID2, _ID3}


# --------------------------------------------------------------------------- #
# Single-item (Reader) chat
# --------------------------------------------------------------------------- #


def test_item_chat_uses_transcript_and_no_tools(client, monkeypatch):
    """item_id chat runs the tool-less agent with the transcript as
    instructions, and never calls a search tool."""
    monkeypatch.setattr(
        "merlin.services.library.get_item",
        lambda _id: {
            "id": "item-1",
            "source_type": "youtube",
            "title": "DJI moats",
            "channel": "Some Channel",
            "summary": "A short overview.",
            "raw_content": "UNIQUE_TRANSCRIPT_TOKEN the speaker explains the moat.",
        },
    )

    captured: dict = {}
    _patch_model(monkeypatch, _text_model("It explains the moat.", captured))

    resp = client.post(
        "/api/chat",
        json=_chat_body("what's the moat?", filters={"item_id": "item-1"}),
    )
    assert resp.status_code == 200
    types = _sse_types(resp.text)
    assert "text-delta" in types
    # The Reader agent has no tools registered.
    assert captured["tool_count"] == 0
    # No consolidated citations on the single-item path (already on the item).
    assert "data-citations" not in types


def test_item_chat_missing_item_returns_400(client, monkeypatch):
    monkeypatch.setattr("merlin.services.library.get_item", lambda _id: None)
    _patch_model(monkeypatch, _text_model("unused"))

    resp = client.post(
        "/api/chat",
        json=_chat_body("q", filters={"item_id": "nope"}),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"


# --------------------------------------------------------------------------- #
# Service-layer unit checks
# --------------------------------------------------------------------------- #


def test_item_instructions_embeds_transcript(monkeypatch):
    from merlin.services import chat as chat_service

    monkeypatch.setattr(
        "merlin.services.library.get_item",
        lambda _id: {
            "id": "item-1",
            "source_type": "youtube",
            "title": "DJI moats",
            "summary": "A short overview.",
            "raw_content": "UNIQUE_TRANSCRIPT_TOKEN explains the moat.",
        },
    )
    instructions = chat_service.item_instructions("item-1")
    assert "UNIQUE_TRANSCRIPT_TOKEN" in instructions
    assert "A short overview." in instructions


def test_item_instructions_missing_raises():
    from merlin.services import chat as chat_service

    with pytest.raises(ValueError, match="not found"):
        # No monkeypatch → real lookup against the (empty) temp DB.
        chat_service.item_instructions("does-not-exist")


# --------------------------------------------------------------------------- #
# Sync one-shot answer() — the archived Streamlit engine room's path.
# --------------------------------------------------------------------------- #


class _FakeChunk:
    def __init__(self, content):
        self.content = content


class _FakeLLM:
    def __init__(self, captured):
        self._captured = captured

    def stream(self, messages):
        self._captured["messages"] = messages
        yield _FakeChunk("answer")


def test_sync_answer_library_path_retrieves(monkeypatch, make_item):
    from merlin.config import settings
    from merlin.services import chat as chat_service

    make_item(title="A moat video", summary="Discussion of moats and edges.")
    captured: dict = {}
    monkeypatch.setattr(settings, "llm", _FakeLLM(captured))

    tokens, citations = chat_service.answer("tell me about moats", [], {})
    assert "".join(tokens) == "answer"
    assert len(citations) >= 1
    # The retrieved context made it into the system prompt.
    assert "moat" in captured["messages"][0]["content"].lower()


def test_sync_answer_item_path_uses_transcript_skips_retrieval(monkeypatch):
    from merlin.config import settings
    from merlin.services import chat as chat_service

    monkeypatch.setattr(
        "merlin.services.library.get_item",
        lambda _id: {
            "id": "item-1",
            "source_type": "youtube",
            "title": "DJI moats",
            "summary": "Overview.",
            "raw_content": "UNIQUE_TRANSCRIPT_TOKEN explains the moat.",
        },
    )

    def boom(*a, **k):
        raise AssertionError("retriever must not run on the item path")

    monkeypatch.setattr(chat_service._retriever, "retrieve", boom)
    captured: dict = {}
    monkeypatch.setattr(settings, "llm", _FakeLLM(captured))

    tokens, citations = chat_service.answer("gist?", [], {"item_id": "item-1"})
    assert "".join(tokens) == "answer"
    assert citations == []
    assert "UNIQUE_TRANSCRIPT_TOKEN" in captured["messages"][0]["content"]
