"""Background chat turns (`merlin.services.chat_turns`), driven directly on an
event loop with the golden chunk logs as the stream — no HTTP, no model.

The router-level behaviour (POST/stream/stop/409) is in test_chat.py.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from merlin.services import chat_history, chat_turns

FIXTURES = Path(__file__).parent / "fixtures" / "chat_streams"
SENT_AT = 1_791_851_280_000

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _log(name: str) -> list[str]:
    return [
        line
        for line in (FIXTURES / f"{name}.chunks.jsonl").read_text().splitlines()
        if line.strip()
    ]


def _expected_parts(name: str) -> list[dict]:
    return json.loads((FIXTURES / f"{name}.expected.json").read_text())["parts"]


async def _stream(lines: list[str], *, hang: bool = False):
    for line in lines:
        await asyncio.sleep(0)
        yield line
    if hang:
        await asyncio.sleep(3600)


def _question(text: str = "what about moats?") -> list[dict]:
    return [{"id": "u1", "role": "user", "parts": [{"type": "text", "text": text}]}]


def _types(parts: list[dict]) -> list[str]:
    return [p["type"] for p in parts]


def _part(parts: list[dict], kind: str) -> dict | None:
    return next((p for p in parts if p["type"] == kind), None)


async def _saved(thread_id: str) -> list[dict]:
    thread = await asyncio.to_thread(chat_history.get_thread, thread_id)
    return thread["messages"]


async def _until(predicate, timeout: float = 2.0) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.005)


_OWN_PARTS = {"data-work-timing", "data-message-time", "data-error"}


async def test_answer_is_saved_after_the_reader_leaves():
    turn = await chat_turns.start_turn(
        "t1", _question(), _stream(_log("tool_loop")), sent_at=SENT_AT
    )
    # The question is saved before the answer starts.
    assert [m["role"] for m in await _saved("t1")] == ["user"]

    reader = turn.tail()
    await anext(reader)
    await reader.aclose()  # the tab closes after one frame
    await turn.done.wait()

    user, answer = await _saved("t1")
    assert _part(user["parts"], "data-message-time")["data"] == {"ms": SENT_AT}
    assert answer["role"] == "assistant"
    # The SDK-identical message, plus the turn's own closing parts.
    assert [p for p in answer["parts"] if p["type"] not in _OWN_PARTS] == (
        _expected_parts("tool_loop")
    )
    assert _part(answer["parts"], "data-work-timing")["data"] == {"seconds": 0}
    assert _part(answer["parts"], "data-message-time") is not None
    assert _part(answer["parts"], "data-error") is None


async def test_closing_parts_stream_before_finish_and_replay():
    turn = await chat_turns.start_turn("t1", _question(), _stream(_log("plain")))
    await turn.done.wait()

    frames = [f async for f in turn.tail()]
    assert frames == turn.frames
    assert frames[-1] == "data: [DONE]\n\n"
    types = [json.loads(f[6:])["type"] for f in frames[:-1]]
    assert types[-3:] == ["finish-step", "data-message-time", "finish"]
    # No tool or reasoning work → no work timing.
    assert "data-work-timing" not in types


async def test_error_turn_saves_partial_answer_with_marker():
    turn = await chat_turns.start_turn("t1", _question(), _stream(_log("step_limit")))
    await turn.done.wait()

    _, answer = await _saved("t1")
    assert _part(answer["parts"], "data-error")["data"] == {
        "reason": "error",
        "message": "The next request would exceed the request_limit of 1",
    }
    assert _part(answer["parts"], "tool-search_library")["state"] == "output-available"


async def test_stop_saves_partial_answer_settled():
    turn = await chat_turns.start_turn(
        "t1", _question(), _stream(_log("truncated"), hang=True)
    )
    await _until(lambda: any("there" in f for f in turn.frames))

    assert await chat_turns.stop_turn("t1") is True
    assert turn.closed

    _, answer = await _saved("t1")
    assert _part(answer["parts"], "text") == {
        "type": "text",
        "text": "Hello there",
        "state": "done",
    }
    assert _part(answer["parts"], "data-error")["data"]["reason"] == "stopped"
    # Live readers get a proper ending too.
    tail_types = [json.loads(f[6:])["type"] for f in turn.frames[-4:-1]]
    assert tail_types == ["data-error", "data-message-time", "finish"]
    assert turn.frames[-1] == "data: [DONE]\n\n"
    assert await chat_turns.stop_turn("t1") is False  # nothing running now


async def test_second_turn_on_a_busy_thread_is_refused():
    await chat_turns.start_turn("t1", _question(), _stream([], hang=True))
    assert chat_turns.registry.running("t1")
    with pytest.raises(chat_turns.TurnBusy):
        await chat_turns.start_turn("t1", _question(), _stream(_log("plain")))
    await chat_turns.stop_turn("t1")
    assert not chat_turns.registry.running("t1")


async def test_after_work_runs_once_the_answer_is_saved():
    seen: list[int] = []

    def record() -> None:
        thread = chat_history.get_thread("t1")
        seen.append(len(thread["messages"]))

    turn = await chat_turns.start_turn(
        "t1", _question(), _stream(_log("plain")), after=[record]
    )
    await turn.task
    assert seen == [2]


async def test_finished_turn_is_forgotten_after_grace(monkeypatch):
    monkeypatch.setattr(chat_turns, "registry", chat_turns.TurnRegistry(grace=0))
    turn = await chat_turns.start_turn("t1", _question(), _stream(_log("plain")))
    await turn.done.wait()
    await asyncio.sleep(0.01)
    assert chat_turns.registry.get("t1") is None


async def test_thread_list_marks_running_turn_active():
    await chat_turns.start_turn("t1", _question(), _stream([], hang=True))
    [row] = await asyncio.to_thread(chat_history.list_threads)
    assert row["active"] is True
    await chat_turns.stop_turn("t1")
    [row] = await asyncio.to_thread(chat_history.list_threads)
    assert row["active"] is False
