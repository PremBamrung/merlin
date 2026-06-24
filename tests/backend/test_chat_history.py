"""Chat-history persistence — the continuable-threads feature.

Exercises the real router → `merlin.services.chat_history` → temp-SQLite path
(schema built by the real Alembic migrations `005` + `006`), plus a continuation
check
that a stored assistant turn with a tool-call/tool-result pair replays through
`/api/chat` without an orphaned-tool-call error (the spike's invariant).
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _no_title_network(monkeypatch):
    """Keep `generate_title` offline: make the chat model unbuildable so the real
    `generate_title` falls into its best-effort `except` and returns None. Tests
    that want a concrete title patch `chat_history.generate_title` directly."""

    def _boom():
        raise RuntimeError("no chat model in tests")

    monkeypatch.setattr("merlin.rag.model.build_chat_model", _boom, raising=True)


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


def _patch_model(monkeypatch, model):
    monkeypatch.setattr(
        "merlin.services.chat.build_chat_model", lambda: model, raising=True
    )


def _has_tool_return(messages) -> bool:
    return any(
        getattr(p, "part_kind", "") == "tool-return"
        for m in messages
        for p in getattr(m, "parts", [])
    )


def _search_then_answer_model(query: str, answer: str):
    """Streaming model: call search_library(query) once, then answer."""
    from pydantic_ai.models.function import DeltaToolCall, FunctionModel

    async def stream_fn(messages, info):
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


def _user(text: str, mid: str = "u1") -> dict:
    return {"id": mid, "role": "user", "parts": [{"type": "text", "text": text}]}


def _assistant(text: str, mid: str = "a1", extra_parts: list | None = None) -> dict:
    parts = [{"type": "text", "text": text}, *(extra_parts or [])]
    return {"id": mid, "role": "assistant", "parts": parts}


# --------------------------------------------------------------------------- #
# Service-layer CRUD
# --------------------------------------------------------------------------- #


def test_save_get_list_roundtrip(client):
    from merlin.services import chat_history

    msgs = [_user("hello moats"), _assistant("Moats are durable advantages.")]
    res = chat_history.save_thread("t1", msgs)
    assert res["id"] == "t1"

    got = chat_history.get_thread("t1")
    assert got is not None
    assert [m["role"] for m in got["messages"]] == ["user", "assistant"]
    # Parts round-trip verbatim (JSON in, JSON out).
    assert got["messages"][0]["parts"][0]["text"] == "hello moats"

    listed = chat_history.list_threads()
    assert len(listed) == 1
    assert listed[0]["id"] == "t1"
    assert listed[0]["message_count"] == 2
    assert listed[0]["preview"] == "hello moats"  # titleless → preview fallback


def test_save_replaces_messages_and_bumps_order(client):
    from merlin.services import chat_history

    chat_history.save_thread("a", [_user("first a")])
    chat_history.save_thread("b", [_user("first b")])
    # Re-saving 'a' with more turns replaces (not appends) and moves it to top.
    chat_history.save_thread(
        "a", [_user("first a"), _assistant("reply"), _user("again", "u2")]
    )

    got = chat_history.get_thread("a")
    assert len(got["messages"]) == 3  # replaced wholesale, no duplicates

    ids = [t["id"] for t in chat_history.list_threads()]
    assert ids[0] == "a"  # most recently updated first


def test_rename_and_delete_cascade(client):
    from sqlalchemy import text

    from merlin.db.engine import engine
    from merlin.services import chat_history

    chat_history.save_thread("t1", [_user("hi"), _assistant("yo")])
    assert chat_history.rename_thread("t1", "My chat") is True
    assert chat_history.get_thread("t1")["title"] == "My chat"

    assert chat_history.delete_thread("t1") is True
    assert chat_history.get_thread("t1") is None
    # Cascade removed the messages too.
    with engine.begin() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM chat_messages")).scalar()
    assert n == 0

    # Missing-thread operations are falsey, not exceptions.
    assert chat_history.rename_thread("nope", "x") is False
    assert chat_history.delete_thread("nope") is False


def test_title_generated_out_of_band_on_first_save(client, monkeypatch):
    from merlin.services import chat_history

    monkeypatch.setattr(chat_history, "generate_title", lambda _t: "Moat Strategies")
    # save_thread no longer generates the title itself (it's a slow LLM call) — it
    # flags that one is needed; the caller runs generation out of band.
    res = chat_history.save_thread("t1", [_user("tell me about moats")])
    assert res["needs_title"] is True
    assert chat_history.get_thread("t1")["title"] is None

    chat_history.generate_and_store_title("t1")
    assert chat_history.get_thread("t1")["title"] == "Moat Strategies"

    # A later save must NOT flag for regeneration (title already set), and a stray
    # generate_and_store_title call is a no-op — patch to a sentinel that would
    # fail the assertion if used.
    monkeypatch.setattr(chat_history, "generate_title", lambda _t: "SHOULD-NOT-BE-USED")
    res2 = chat_history.save_thread(
        "t1", [_user("tell me about moats"), _assistant("...")]
    )
    assert res2["needs_title"] is False
    chat_history.generate_and_store_title("t1")
    assert chat_history.get_thread("t1")["title"] == "Moat Strategies"


def test_generate_title_is_best_effort(client):
    """No API key configured → generate_title swallows the error and returns None
    (the save still succeeds, titleless)."""
    from merlin.services import chat_history

    assert chat_history.generate_title("anything") is None
    chat_history.save_thread("t1", [_user("q")])
    assert chat_history.get_thread("t1")["title"] is None


# --------------------------------------------------------------------------- #
# HTTP endpoints
# --------------------------------------------------------------------------- #


def test_endpoints_put_get_list_delete(client, monkeypatch):
    from merlin.services import chat_history

    monkeypatch.setattr(chat_history, "generate_title", lambda _t: "Titled")

    body = {"messages": [_user("hello"), _assistant("hi there")]}
    r = client.put("/api/chat/threads/t1", json=body)
    assert r.status_code == 200
    # Title is generated by a background task, so the PUT response has none yet.
    assert r.json() == {"id": "t1", "title": None}

    # The TestClient runs the scheduled background task after the response, so by
    # the GET the generated title is stored.
    r = client.get("/api/chat/threads/t1")
    assert r.status_code == 200
    detail = r.json()
    assert detail["title"] == "Titled"
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]

    r = client.get("/api/chat/threads")
    assert r.status_code == 200
    assert any(t["id"] == "t1" for t in r.json())

    r = client.delete("/api/chat/threads/t1")
    assert r.status_code == 204
    assert client.get("/api/chat/threads/t1").status_code == 404


def test_get_missing_thread_404(client):
    r = client.get("/api/chat/threads/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_rename_endpoint(client):
    from merlin.services import chat_history

    chat_history.save_thread("t1", [_user("hi")])
    r = client.patch("/api/chat/threads/t1", json={"title": "Renamed"})
    assert r.status_code == 200
    assert r.json()["title"] == "Renamed"
    missing = client.patch("/api/chat/threads/nope", json={"title": "x"})
    assert missing.status_code == 404


def test_citation_data_parts_persist_verbatim(client):
    """The custom `data-citations` part survives the round-trip — the whole point
    of client-driven persistence (server `dump_messages` would drop it)."""
    from merlin.services import chat_history

    cite_part = {
        "type": "data-citations",
        "data": {
            "items": [
                {
                    "item_id": "x",
                    "title": "T",
                    "source_type": "youtube",
                    "snippet": "s",
                    "score": 1.0,
                }
            ]
        },
    }
    chat_history.save_thread(
        "t1", [_user("q"), _assistant("answer", extra_parts=[cite_part])]
    )
    asst = chat_history.get_thread("t1")["messages"][1]
    assert any(p["type"] == "data-citations" for p in asst["parts"])


# --------------------------------------------------------------------------- #
# Continuation — the spike invariant (tool-call/result pairs replay cleanly)
# --------------------------------------------------------------------------- #


def test_stored_tool_turn_continues_without_orphaned_tool_call(
    client, monkeypatch, make_item
):
    """A reopened thread sends its stored history (incl. a completed tool
    call/result) plus a new user turn to /api/chat; the adapter must accept it
    and the model continues, with no orphaned-tool-call error."""
    make_item(title="A video about moats", summary="moats and edges")
    _patch_model(monkeypatch, _search_then_answer_model("moats", "Following up."))

    # Stored assistant turn: a search tool call that already produced output
    # (camelCase keys, matching the Vercel AI SDK wire format / useChat state).
    prior_tool_part = {
        "type": "tool-search_library",
        "toolCallId": "call-prev",
        "state": "output-available",
        "input": {"query": "moats"},
        "output": "[some-id] A video about moats",
    }
    body = {
        "id": "t1",
        "trigger": "submit-message",
        "messages": [
            _user("what about moats?", "u1"),
            _assistant("Moats are durable.", "a1", extra_parts=[prior_tool_part]),
            _user("can you expand?", "u2"),
        ],
    }

    resp = client.post("/api/chat", json=body)
    assert resp.status_code == 200
    types = _sse_types(resp.text)
    assert "text-delta" in types
    assert "finish" in types
    assert "error" not in types  # no orphaned tool_call_id / replay failure
