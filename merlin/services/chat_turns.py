"""Background chat turns — a library-chat answer that outlives its HTTP request.

A turn runs in its own `asyncio.Task`, so closing the tab, reloading or
switching threads no longer cancels it (Starlette cancels a streaming response's
body on disconnect). Every SSE frame is kept on the `Turn`, and any number of
readers *tail* it: the `POST /api/chat` that started it, and later
`GET /api/chat/{id}/stream` reconnects, which replay from the first frame and
then follow live.

The server now owns persistence: the request's messages are saved when the turn
starts (so the question survives anything) and the reduced assistant message is
saved when it ends (`chat_stream_reducer` builds exactly what the browser
builds). Just before the stream's `finish` the turn adds its own data-parts,
which reach the live client and the saved copy alike:
`data-work-timing` (send → first answer text), `data-message-time` (finish
time) and, for an errored or stopped turn, `data-error`.

The registry is in-memory: the app runs one process. A restart mid-turn loses
the turn; the thread keeps the question with no answer, and Retry covers it.

Framework-free: it takes the encoded chunk stream (JSON strings) from the API
layer and never imports `fastapi`.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass, field
import json
import logging
import time

from merlin.services import chat_history
from merlin.services.chat import MESSAGE_TIME_PART
from merlin.services.chat_stream_reducer import ChunkReducer

logger = logging.getLogger(__name__)

__all__ = [
    "ERROR_PART",
    "Turn",
    "TurnBusy",
    "WORK_TIMING_PART",
    "registry",
    "start_turn",
    "stop_turn",
]

# Data-parts the turn adds (web/src/hooks/useAgentChat.ts reads them).
WORK_TIMING_PART = "data-work-timing"
ERROR_PART = "data-error"

# How long a finished turn stays replayable, so a reconnect racing the finish
# still gets the answer instead of a 204.
GRACE_SECONDS = 60.0

_DONE_FRAME = "data: [DONE]\n\n"


class TurnBusy(RuntimeError):
    """The thread already has a turn running."""


def _frame(payload: str) -> str:
    return f"data: {payload}\n\n"


def _dump(chunk: dict) -> str:
    return json.dumps(chunk, separators=(",", ":"), ensure_ascii=False)


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass(eq=False)
class Turn:
    """One running (or just finished) answer and its frame log."""

    thread_id: str
    # How many messages the thread holds once this answer lands. A reconnecting
    # client that already has this many has the answer: nothing to resume.
    message_count: int
    frames: list[str] = field(default_factory=list)
    closed: bool = False
    stop_requested: bool = False
    # Past the stream: saving. A Stop now would only interrupt the save.
    winding_down: bool = False
    task: asyncio.Task | None = None
    # Set once the answer is saved and the frame log is complete.
    done: asyncio.Event = field(default_factory=asyncio.Event)
    _changed: asyncio.Event = field(default_factory=asyncio.Event)

    def push(self, frame: str) -> None:
        self.frames.append(frame)
        self._wake()

    def close(self) -> None:
        self.closed = True
        self.done.set()
        self._wake()

    def _wake(self) -> None:
        changed, self._changed = self._changed, asyncio.Event()
        changed.set()

    async def tail(self) -> AsyncIterator[str]:
        """Every frame from the first, then live ones until the turn closes."""
        sent = 0
        while True:
            if sent < len(self.frames):
                batch = self.frames[sent:]
                sent += len(batch)
                for frame in batch:
                    yield frame
                continue
            if self.closed:
                return
            await self._changed.wait()


class TurnRegistry:
    """The turns by thread id: running ones, plus finished ones for a grace
    period."""

    def __init__(self, grace: float = GRACE_SECONDS) -> None:
        self.grace = grace
        self._turns: dict[str, Turn] = {}

    def get(self, thread_id: str) -> Turn | None:
        return self._turns.get(thread_id)

    def running(self, thread_id: str) -> bool:
        turn = self._turns.get(thread_id)
        return turn is not None and not turn.closed

    def running_ids(self) -> set[str]:
        return {tid for tid, turn in self._turns.items() if not turn.closed}

    def add(self, turn: Turn) -> None:
        if self.running(turn.thread_id):
            raise TurnBusy(turn.thread_id)
        self._turns[turn.thread_id] = turn

    def discard(self, turn: Turn) -> None:
        if self._turns.get(turn.thread_id) is turn:
            del self._turns[turn.thread_id]

    def expire(self, turn: Turn) -> None:
        """Forget a finished turn after the grace period."""
        asyncio.get_running_loop().call_later(self.grace, self.discard, turn)


registry = TurnRegistry()

# Fire-and-forget tasks (title generation) — held so they aren't collected.
_background: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.ensure_future(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


def _stamp_last_user(messages: list[dict], sent_at: object) -> list[dict]:
    """Give the newest user message its send time, unless it has one — the
    same `sent_at` the agent was shown, so later turns replay it unchanged."""
    out = list(messages)
    for i in range(len(out) - 1, -1, -1):
        msg = out[i]
        if msg.get("role") != "user":
            continue
        parts = list(msg.get("parts") or [])
        if not any(
            isinstance(p, dict) and p.get("type") == MESSAGE_TIME_PART for p in parts
        ):
            ms = (
                sent_at
                if isinstance(sent_at, (int, float)) and not isinstance(sent_at, bool)
                else _now_ms()
            )
            parts.append({"type": MESSAGE_TIME_PART, "data": {"ms": int(ms)}})
            out[i] = {**msg, "parts": parts}
        break
    return out


def _is_work_part(part: dict) -> bool:
    kind = part.get("type", "")
    return kind == "reasoning" or kind == "dynamic-tool" or kind.startswith("tool-")


async def start_turn(
    thread_id: str,
    messages: list[dict],
    payloads: AsyncIterator[str],
    *,
    sent_at: object = None,
    after: Iterable[Callable[[], object]] = (),
) -> Turn:
    """Save the request's messages, then run the answer in the background.

    `payloads` is the encoded chunk stream (one JSON object per item, without
    the `[DONE]` sentinel); it's only iterated by the turn's task. `after` holds
    zero-argument callables run in a worker thread once the answer is saved —
    out-of-band work such as usage capture; the API layer may append to it
    while the run is in progress. Raises `TurnBusy` if the thread already has a
    turn running.
    """
    messages = _stamp_last_user(messages, sent_at)
    turn = Turn(thread_id=thread_id, message_count=len(messages) + 1)
    registry.add(turn)
    try:
        saved = await asyncio.to_thread(chat_history.save_thread, thread_id, messages)
    except BaseException:
        registry.discard(turn)
        raise
    if saved.get("needs_title"):
        _spawn(asyncio.to_thread(chat_history.generate_and_store_title, thread_id))
    turn.task = asyncio.ensure_future(_drive(turn, messages, payloads, after))
    # Safety net: a task cancelled before its first step never enters `_drive`.
    turn.task.add_done_callback(lambda _t: None if turn.closed else _abandon(turn))
    return turn


def _abandon(turn: Turn) -> None:
    turn.push(_DONE_FRAME)
    turn.close()
    registry.expire(turn)


async def stop_turn(thread_id: str, timeout: float = 10.0) -> bool:
    """Cancel a running turn and wait (bounded) for its partial answer to be
    saved. False when nothing was running."""
    turn = registry.get(thread_id)
    if turn is None or turn.closed:
        return False
    if not turn.stop_requested and not turn.winding_down and turn.task is not None:
        turn.stop_requested = True
        turn.task.cancel()
    try:
        await asyncio.wait_for(asyncio.shield(turn.done.wait()), timeout)
    except TimeoutError:
        logger.warning(
            "chat turn %s did not settle within %ss of Stop", thread_id, timeout
        )
    return True


async def _drive(
    turn: Turn,
    messages: list[dict],
    payloads: AsyncIterator[str],
    after: Iterable[Callable[[], object]],
) -> None:
    reducer = ChunkReducer()
    started = time.monotonic()
    work_seconds: float | None = None
    finished = False

    def closing_parts() -> list[dict]:
        """The turn's own data-parts, added just before `finish`."""
        parts: list[dict] = []
        if turn.stop_requested:
            parts.append(
                {
                    "type": ERROR_PART,
                    "data": {"reason": "stopped", "message": "Stopped"},
                }
            )
        elif reducer.error_text is not None:
            parts.append(
                {
                    "type": ERROR_PART,
                    "data": {"reason": "error", "message": reducer.error_text},
                }
            )
        if work_seconds is not None and any(_is_work_part(p) for p in reducer.parts):
            parts.append(
                {
                    "type": WORK_TIMING_PART,
                    "data": {"seconds": max(0, round(work_seconds))},
                }
            )
        parts.append({"type": MESSAGE_TIME_PART, "data": {"ms": _now_ms()}})
        return parts

    def emit(chunk: dict, payload: str | None = None) -> None:
        reducer.add(chunk)
        turn.push(_frame(payload if payload is not None else _dump(chunk)))

    try:
        async for payload in payloads:
            chunk = json.loads(payload)
            kind = chunk.get("type")
            if kind == "finish" and not finished:
                for part in closing_parts():
                    emit(part)
                finished = True
            emit(chunk, payload)
            if work_seconds is None and kind == "text-delta" and chunk.get("delta"):
                work_seconds = time.monotonic() - started
    except asyncio.CancelledError:
        # Stop (or shutdown): keep what streamed. Clear the cancellation so the
        # save below can still await.
        task = asyncio.current_task()
        if task is not None:
            task.uncancel()
        turn.stop_requested = True
    except (
        Exception
    ) as exc:  # the adapter reports run errors as chunks; this is a broken stream
        logger.exception("chat turn %s stream failed", turn.thread_id)
        if reducer.error_text is None:
            emit({"type": "error", "errorText": str(exc) or type(exc).__name__})
    finally:
        turn.winding_down = True

    try:
        if not finished:
            for part in closing_parts():
                emit(part)
            emit(
                {
                    "type": "finish",
                    "finishReason": "error" if reducer.error_text else "other",
                }
            )
        turn.push(_DONE_FRAME)
        await _save_answer(turn, messages, reducer)
    finally:
        turn.close()
        registry.expire(turn)

    for fn in list(after):
        try:
            await asyncio.to_thread(fn)
        except Exception:  # never let bookkeeping surface
            logger.exception("chat turn %s: after-work failed", turn.thread_id)


async def _save_answer(turn: Turn, messages: list[dict], reducer: ChunkReducer) -> None:
    reducer.close()
    answer = reducer.message
    saved = [
        *messages,
        {"id": answer["id"], "role": "assistant", "parts": answer["parts"]},
    ]
    try:
        await asyncio.to_thread(chat_history.save_thread, turn.thread_id, saved)
    except Exception:
        logger.exception("chat turn %s: saving the answer failed", turn.thread_id)
