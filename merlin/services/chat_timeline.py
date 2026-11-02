"""Per-step timing of one agent turn, folded from its AI SDK chunk stream.

`chat_turns` already sees every chunk of a library-chat turn go by; this folds
their arrival times into a breakdown of where the turn's wall-clock went, so a
slow answer can be attributed (model waits vs thinking vs tool I/O vs number of
steps) instead of guessed at. Saved on the answer as a `data-turn-timeline`
part and logged as one line per turn. The UI ignores the part.

How the chunk stream maps to time — Pydantic AI's Vercel adapter emits
`start-step` when a model response's **first part arrives**, not when the
request is sent. So a step's request is taken to start when the previous step
was done (its last model chunk, or its last tool result — tools run after the
response completes), and the turn's first request at the turn's start:

- ``wait_ms``      request → first streamed chunk (time to first token,
                   including any thinking the model doesn't stream)
- ``stream_ms``    first → last model chunk of the step (streamed reasoning,
                   text and tool-call arguments)
- ``reasoning_ms`` time inside ``reasoning-start``…``reasoning-end`` segments
- ``tools``        per call, ``tool-input-available`` → its output/error

Turn totals: ``total_ms`` (start → finish), ``first_text_ms`` (start → first
answer text — what the UI's work timer shows), ``model_ms`` (Σ wait+stream) and
``tools_ms`` (Σ per-step wall time of the tool calls, parallel calls counted
once).

Framework-free; takes plain chunk dicts and explicit timestamps (seconds from
any monotonic clock), so it's testable without a clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TIMELINE_PART = "data-turn-timeline"

# Chunks the model streams within a step (everything else is protocol framing,
# tool results or data-parts the server appends).
_MODEL_CHUNKS = {
    "text-start",
    "text-delta",
    "text-end",
    "reasoning-start",
    "reasoning-delta",
    "reasoning-end",
    "tool-input-start",
    "tool-input-delta",
    "tool-input-available",
}
_TOOL_DONE = {"tool-output-available", "tool-output-error", "tool-input-error"}


def _ms(seconds: float) -> int:
    return max(0, round(seconds * 1000))


@dataclass
class _Tool:
    name: str
    start: float
    end: float | None = None


@dataclass
class _Step:
    requested: float
    first: float
    last: float
    reasoning: float = 0.0
    reasoning_open: float | None = None
    tools: dict[str, _Tool] = field(default_factory=dict)

    def done_at(self) -> float:
        """When the next request could go out: the model is done and every
        tool call has returned."""
        ends = [t.end for t in self.tools.values() if t.end is not None]
        return max([self.last, *ends])

    def tools_wall(self) -> float:
        spans = [(t.start, t.end) for t in self.tools.values() if t.end is not None]
        if not spans:
            return 0.0
        return max(e for _, e in spans) - min(s for s, _ in spans)

    def as_dict(self) -> dict:
        return {
            "wait_ms": _ms(self.first - self.requested),
            "stream_ms": _ms(self.last - self.first),
            "reasoning_ms": _ms(self.reasoning),
            "tools": [
                {
                    "name": t.name,
                    "ms": _ms(t.end - t.start) if t.end is not None else None,
                }
                for t in self.tools.values()
            ],
        }


class TurnTimeline:
    """Accumulates one turn's chunk timings; see the module docstring."""

    def __init__(self, started: float) -> None:
        self._started = started
        self._steps: list[_Step] = []
        self._first_text: float | None = None
        self._finished: float | None = None
        self._last_seen = started

    def add(self, chunk: dict, now: float) -> None:
        kind = chunk.get("type")
        self._last_seen = now
        if kind == "start-step":
            prev = self._steps[-1] if self._steps else None
            requested = prev.done_at() if prev else self._started
            self._steps.append(_Step(requested=requested, first=now, last=now))
            return
        if kind == "finish":
            self._finished = now
            return
        step = self._steps[-1] if self._steps else None
        if step is None:
            return
        if kind in _MODEL_CHUNKS:
            step.last = now
        if kind == "reasoning-start":
            step.reasoning_open = now
        elif kind == "reasoning-end" and step.reasoning_open is not None:
            step.reasoning += now - step.reasoning_open
            step.reasoning_open = None
        elif kind == "text-delta" and self._first_text is None and chunk.get("delta"):
            self._first_text = now
        elif kind == "tool-input-available":
            call_id = chunk.get("toolCallId") or f"call-{len(step.tools)}"
            step.tools[call_id] = _Tool(name=chunk.get("toolName") or "?", start=now)
        elif kind in _TOOL_DONE:
            tool = step.tools.get(chunk.get("toolCallId") or "")
            if tool is not None and tool.end is None:
                tool.end = now

    def to_dict(self) -> dict:
        end = self._finished if self._finished is not None else self._last_seen
        steps = [s.as_dict() for s in self._steps]
        return {
            "total_ms": _ms(end - self._started),
            "first_text_ms": (
                _ms(self._first_text - self._started)
                if self._first_text is not None
                else None
            ),
            "model_ms": sum(s["wait_ms"] + s["stream_ms"] for s in steps),
            "tools_ms": _ms(sum(s.tools_wall() for s in self._steps)),
            "steps": steps,
        }


def describe(timeline: dict) -> str:
    """One human line for a timeline dict (logs, the summary script)."""

    def sec(ms: int | None) -> str:
        return "?" if ms is None else f"{ms / 1000:.1f}s"

    head = f"{sec(timeline.get('total_ms'))}"
    if timeline.get("first_text_ms") is not None:
        head += f" (first text {sec(timeline['first_text_ms'])})"
    head += (
        f" — model {sec(timeline.get('model_ms'))}, "
        f"tools {sec(timeline.get('tools_ms'))}, "
        f"{len(timeline.get('steps') or [])} step(s)"
    )
    parts = [head]
    for i, s in enumerate(timeline.get("steps") or [], 1):
        bit = f"#{i} wait {sec(s['wait_ms'])} stream {sec(s['stream_ms'])}"
        if s.get("reasoning_ms"):
            bit += f" think {sec(s['reasoning_ms'])}"
        if s.get("tools"):
            bit += (
                " ["
                + ", ".join(f"{t['name']} {sec(t['ms'])}" for t in s["tools"])
                + "]"
            )
        parts.append(bit)
    return " · ".join(parts)
