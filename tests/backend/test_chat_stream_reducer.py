"""The server-side chunk reducer must build exactly the message the browser does.

Golden fixtures: each `*.chunks.jsonl` is a real `VercelAIAdapter` chunk log
(fake model), and its `*.expected.json` is the UIMessage the AI SDK's own
`readUIMessageStream` reduced it to. To add a case: run
`VercelAIAdapter(..., sdk_version=6).run_stream(model=FunctionModel(...))` and
write each `chunk.encode(6)` (minus `[DONE]`) as a line, then pipe the parsed
lines through `readUIMessageStream` from `web/node_modules/ai` in a node script
and save its last message as the expected JSON.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from merlin.services.chat_stream_reducer import ChunkReducer

FIXTURES = Path(__file__).parent / "fixtures" / "chat_streams"
CASES = sorted(
    p.name.removesuffix(".chunks.jsonl") for p in FIXTURES.glob("*.chunks.jsonl")
)


def _chunks(name: str) -> list[dict]:
    lines = (FIXTURES / f"{name}.chunks.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _reduce(name: str) -> ChunkReducer:
    reducer = ChunkReducer()
    for chunk in _chunks(name):
        reducer.add(chunk)
    return reducer


def test_fixtures_present():
    assert {
        "plain",
        "tool_loop",
        "reasoning",
        "error",
        "step_limit",
        "truncated",
    } <= set(CASES)


@pytest.mark.parametrize("name", CASES)
def test_matches_ai_sdk(name):
    expected = json.loads((FIXTURES / f"{name}.expected.json").read_text())
    assert _reduce(name).message == expected


def test_records_error_and_finish_reason():
    reducer = _reduce("step_limit")
    assert reducer.error_text == "The next request would exceed the request_limit of 1"
    assert reducer.finish_reason == "error"
    assert _reduce("plain").error_text is None


def test_close_settles_a_truncated_stream():
    reducer = _reduce("truncated")
    assert reducer.parts[-1]["state"] == "streaming"
    reducer.close()
    assert reducer.parts[-1] == {"type": "text", "text": "Hello there", "state": "done"}


def test_close_fails_unfinished_tool_calls():
    reducer = _reduce("tool_loop")
    reducer.add({"type": "start-step"})
    reducer.add({"type": "tool-input-start", "toolCallId": "c9", "toolName": "search"})
    reducer.close()
    part = reducer.parts[-1]
    assert part["type"] == "tool-search"
    assert part["state"] == "output-error"
    assert part["errorText"] == "Interrupted."
    # Finished calls are untouched.
    assert reducer.parts[1]["state"] == "output-available"


def test_data_part_with_id_is_replaced_in_place():
    reducer = ChunkReducer("m1")
    reducer.add({"type": "data-progress", "id": "p", "data": {"n": 1}})
    reducer.add({"type": "text-start", "id": "t"})
    reducer.add({"type": "data-progress", "id": "p", "data": {"n": 2}})
    reducer.add({"type": "data-note", "data": 1, "transient": True})
    assert reducer.message["parts"] == [
        {"type": "data-progress", "id": "p", "data": {"n": 2}},
        {"type": "text", "text": "", "state": "streaming"},
    ]
