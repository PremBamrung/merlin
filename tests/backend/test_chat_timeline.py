"""`merlin.services.chat_timeline` — per-step turn timing folded from the chunk
stream, driven with explicit timestamps (no clock)."""

from __future__ import annotations

from merlin.services.chat_timeline import TurnTimeline, describe


def _fold(events: list[tuple[float, dict]], started: float = 0.0) -> dict:
    tl = TurnTimeline(started)
    for t, chunk in events:
        tl.add(chunk, t)
    return tl.to_dict()


# A two-step turn: the model thinks, calls two tools in parallel, then answers.
TOOL_TURN = [
    (0.0, {"type": "start"}),
    (1.5, {"type": "start-step"}),
    (1.5, {"type": "reasoning-start", "id": "r1"}),
    (1.6, {"type": "reasoning-delta", "id": "r1", "delta": "hmm"}),
    (2.5, {"type": "reasoning-end", "id": "r1"}),
    (2.6, {"type": "tool-input-start", "toolCallId": "c1", "toolName": "search"}),
    (
        2.8,
        {"type": "tool-input-available", "toolCallId": "c1", "toolName": "search"},
    ),
    (
        2.9,
        {"type": "tool-input-available", "toolCallId": "c2", "toolName": "get_items"},
    ),
    (3.8, {"type": "tool-output-available", "toolCallId": "c1", "output": "x"}),
    (4.4, {"type": "tool-output-error", "toolCallId": "c2", "errorText": "no"}),
    (9.4, {"type": "finish-step"}),
    (9.4, {"type": "start-step"}),
    (9.4, {"type": "text-start", "id": "t1"}),
    (9.5, {"type": "text-delta", "id": "t1", "delta": "Answer"}),
    (12.0, {"type": "text-end", "id": "t1"}),
    (12.1, {"type": "data-usage", "data": {}}),
    (12.2, {"type": "finish-step"}),
    (12.3, {"type": "finish"}),
]


def test_tool_turn_breakdown():
    tl = _fold(TOOL_TURN)
    assert tl["total_ms"] == 12300
    assert tl["first_text_ms"] == 9500
    first, second = tl["steps"]
    # Step 1's request went out at the turn's start; first chunk at 1.5s.
    assert first["wait_ms"] == 1500
    assert first["stream_ms"] == 1400  # 1.5 → last tool-call arg chunk at 2.9
    assert first["reasoning_ms"] == 1000
    assert first["tools"] == [
        {"name": "search", "ms": 1000},
        {"name": "get_items", "ms": 1500},
    ]
    # Step 2's request went out once the last tool returned (4.4s), not at the
    # (late) finish-step chunk — the adapter only emits that with step 2's
    # first part.
    assert second["wait_ms"] == 5000
    # data-usage is server-appended, not model output: stream ends at text-end.
    assert second["stream_ms"] == 2600
    assert second["tools"] == []
    assert tl["model_ms"] == 1500 + 1400 + 5000 + 2600
    # Parallel calls are counted once: 2.8 → 4.4.
    assert tl["tools_ms"] == 1600


def test_plain_turn_has_one_step_and_no_tools():
    tl = _fold(
        [
            (0.0, {"type": "start"}),
            (2.0, {"type": "start-step"}),
            (2.0, {"type": "text-start", "id": "t"}),
            (2.1, {"type": "text-delta", "id": "t", "delta": "Hi"}),
            (2.5, {"type": "text-end", "id": "t"}),
            (2.6, {"type": "finish-step"}),
            (2.6, {"type": "finish"}),
        ]
    )
    assert tl["first_text_ms"] == 2100
    assert tl["tools_ms"] == 0
    assert [s["wait_ms"] for s in tl["steps"]] == [2000]


def test_unfinished_turn_ends_at_the_last_chunk_and_keeps_pending_tools():
    tl = _fold(
        [
            (0.0, {"type": "start-step"}),
            (
                1.0,
                {"type": "tool-input-available", "toolCallId": "c", "toolName": "s"},
            ),
        ]
    )
    assert tl["total_ms"] == 1000
    assert tl["first_text_ms"] is None
    assert tl["steps"][0]["tools"] == [{"name": "s", "ms": None}]
    assert tl["tools_ms"] == 0


def test_no_steps_before_the_first_response():
    assert _fold([(0.0, {"type": "start"}), (1.0, {"type": "finish"})])["steps"] == []


def test_describe_is_one_readable_line():
    line = describe(_fold(TOOL_TURN))
    assert line.startswith(
        "12.3s (first text 9.5s) — model 10.5s, tools 1.6s, 2 step(s)"
    )
    assert "#1 wait 1.5s stream 1.4s think 1.0s [search 1.0s, get_items 1.5s]" in line
    assert "#2 wait 5.0s stream 2.6s" in line
