"""Chat SSE endpoint — citations → tokens → done, with error frames."""

from __future__ import annotations

import json


def _frames(text: str) -> list[dict]:
    """Parse an SSE body into the list of JSON event objects."""
    out = []
    for block in text.strip().split("\n\n"):
        block = block.strip()
        if block.startswith("data:"):
            out.append(json.loads(block[len("data:") :].strip()))
    return out


def _chunk(**kw):
    from merlin.rag.retriever import RetrievedChunk

    defaults = {
        "knowledge_item_id": "item-1",
        "source_type": "youtube",
        "source_id": "vid1",
        "title": "DJI moats",
        "author": "Some Channel",
        "excerpt": "DJI's edge is its supply chain.",
        "score": 0.9,
    }
    defaults.update(kw)
    return RetrievedChunk(**defaults)


def test_chat_streams_citations_tokens_done(client, monkeypatch):
    def fake_answer(question, history, filters):
        assert question == "What about moats?"
        return iter(["DJI's ", "edge."]), [_chunk()]

    monkeypatch.setattr("merlin.services.chat.answer", fake_answer)

    resp = client.post(
        "/api/chat",
        json={"question": "What about moats?", "history": [], "filters": None},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    frames = _frames(resp.text)
    assert frames[0]["type"] == "citations"
    cite = frames[0]["citations"][0]
    assert cite == {
        "item_id": "item-1",
        "title": "DJI moats",
        "source_type": "youtube",
        "snippet": "DJI's edge is its supply chain.",
        "score": 0.9,
    }
    tokens = [f["text"] for f in frames if f["type"] == "token"]
    assert tokens == ["DJI's ", "edge."]
    assert frames[-1]["type"] == "done"


def test_chat_passes_history_and_filters(client, monkeypatch):
    captured = {}

    def fake_answer(question, history, filters):
        captured.update(history=history, filters=filters)
        return iter(["ok"]), []

    monkeypatch.setattr("merlin.services.chat.answer", fake_answer)

    resp = client.post(
        "/api/chat",
        json={
            "question": "q",
            "history": [{"role": "user", "content": "hi"}],
            "filters": {"source_types": ["youtube"], "tags": ["ai"]},
        },
    )
    assert resp.status_code == 200
    assert captured["history"] == [{"role": "user", "content": "hi"}]
    assert captured["filters"] == {"source_types": ["youtube"], "tags": ["ai"]}
    # Empty citations list is still emitted up front.
    assert _frames(resp.text)[0] == {"type": "citations", "citations": []}


def test_chat_retrieval_valueerror_emits_error_frame(client, monkeypatch):
    def boom(question, history, filters):
        raise ValueError("bad filter")

    monkeypatch.setattr("merlin.services.chat.answer", boom)

    frames = _frames(client.post("/api/chat", json={"question": "q"}).text)
    assert len(frames) == 1
    assert frames[0]["type"] == "error"
    assert frames[0]["error"]["code"] == "invalid_input"
    assert frames[0]["error"]["message"] == "bad filter"


def test_chat_token_stream_failure_emits_error_after_citations(client, monkeypatch):
    def fake_answer(question, history, filters):
        def gen():
            yield "partial "
            raise RuntimeError("LLM exploded")

        return gen(), [_chunk()]

    monkeypatch.setattr("merlin.services.chat.answer", fake_answer)

    frames = _frames(client.post("/api/chat", json={"question": "q"}).text)
    assert frames[0]["type"] == "citations"
    assert frames[1] == {"type": "token", "text": "partial "}
    assert frames[-1]["type"] == "error"
    assert frames[-1]["error"]["code"] == "upstream_error"
