"""Server-Sent Events — the part of the contract OpenAPI can't express.

The **chat** stream is no longer here: `POST /api/chat` now speaks the Vercel AI
SDK data-stream protocol, emitted by `VercelAIAdapter` in `routers/chat.py`.
This module owns the remaining hand-rolled stream:

  * task progress   — `GET /api/tasks/{id}/stream`
                       (progress* → complete|failed|cancelled)

Each frame is one JSON object on a `data:` line, frames separated by a blank
line. The task generator polls `merlin.services.ingest.get_task` server-side —
the simplest cadence with zero changes to the core task queue (§7).
"""

from __future__ import annotations

from collections.abc import Iterator
import json
import time

from merlin.services import ingest as ingest_service

from .errors import error_body

# Server-side poll cadence + safety cap for the task-progress stream. Module
# constants so tests can shrink them (poll interval → 0) without real waits.
TASK_STREAM_POLL_INTERVAL = 0.7  # seconds between get_task() polls
TASK_STREAM_MAX_SECONDS = 600  # close the stream after this long regardless


def format_sse(obj: dict) -> str:
    """Serialise one event object to an SSE `data:` frame."""
    return f"data: {json.dumps(obj)}\n\n"


def task_progress_events(task_id: str) -> Iterator[str]:
    """Yield SSE frames for `GET /api/tasks/{id}/stream` by polling get_task.

    Emits a `progress` frame whenever status/progress/message changes, then a
    terminal `complete` or `failed` frame carrying the full Task object (so the
    client can navigate without a second fetch). Closes on the terminal frame,
    on an unknown id, or after TASK_STREAM_MAX_SECONDS.
    """
    if ingest_service.get_task(task_id) is None:
        yield format_sse(
            {"type": "error", **error_body("not_found", "Task not found.")}
        )
        return

    last_sig = None
    deadline = time.monotonic() + TASK_STREAM_MAX_SECONDS
    while True:
        task = ingest_service.get_task(task_id)
        if task is None:
            yield format_sse(
                {"type": "error", **error_body("not_found", "Task not found.")}
            )
            return

        status = task.get("status")
        if status == "completed":
            yield format_sse({"type": "complete", "task": task})
            return
        if status == "failed":
            yield format_sse({"type": "failed", "task": task})
            return
        if status == "cancelled":
            yield format_sse({"type": "cancelled", "task": task})
            return

        sig = (status, task.get("progress"), task.get("message"))
        if sig != last_sig:
            yield format_sse({"type": "progress", "task": task})
            last_sig = sig

        if time.monotonic() > deadline:
            return
        time.sleep(TASK_STREAM_POLL_INTERVAL)
