"""Server-Sent Events — the part of the contract OpenAPI can't express.

Two one-way (server→client) streams, per FRONTEND_V3_API.md §4:

  * chat tokens     — `POST /api/chat`            (citations → tokens → done)
  * task progress   — `GET /api/tasks/{id}/stream` (progress* → complete|failed)

Each frame is one JSON object on a `data:` line, frames separated by a blank
line. Every object carries a `type` discriminator the client switches on.

The chat generator is driven by `merlin.services.chat.answer` (which retrieves
synchronously, then yields tokens). The task generator polls
`merlin.services.ingest.get_task` server-side — the simplest cadence with zero
changes to the core task queue (§7).
"""

from __future__ import annotations

from collections.abc import Iterator
import json
import time

from merlin.core.logging import logger
from merlin.rag.retriever import RetrievedChunk
from merlin.services import chat as chat_service, ingest as ingest_service

from .errors import error_body

# Server-side poll cadence + safety cap for the task-progress stream. Module
# constants so tests can shrink them (poll interval → 0) without real waits.
TASK_STREAM_POLL_INTERVAL = 0.7  # seconds between get_task() polls
TASK_STREAM_MAX_SECONDS = 600  # close the stream after this long regardless


def format_sse(obj: dict) -> str:
    """Serialise one event object to an SSE `data:` frame."""
    return f"data: {json.dumps(obj)}\n\n"


def _serialize_citation(chunk: RetrievedChunk) -> dict:
    """Map a retriever chunk to the wire `Citation` (§2.3)."""
    return {
        "item_id": chunk.knowledge_item_id,
        "title": chunk.title,
        "source_type": chunk.source_type,
        "snippet": chunk.excerpt,
        "score": chunk.score,
    }


def chat_event_stream(
    question: str,
    history: list[dict],
    filters: dict,
) -> Iterator[str]:
    """Yield SSE frames for `POST /api/chat`: citations, tokens, then done.

    `chat_service.answer` retrieves chunks synchronously before returning the
    token generator, so retrieval failures surface as an `error` frame *before*
    any tokens; an LLM failure mid-stream surfaces as an `error` frame after the
    citations. Either way the client renders one `ErrorState`.
    """
    try:
        token_gen, chunks = chat_service.answer(question, history, filters)
    except ValueError as exc:
        yield format_sse({"type": "error", **error_body("invalid_input", str(exc))})
        return
    except Exception as exc:  # retrieval / setup failure
        logger.exception(f"chat retrieval failed: {exc}")
        yield format_sse({"type": "error", **error_body("upstream_error", str(exc))})
        return

    yield format_sse(
        {"type": "citations", "citations": [_serialize_citation(c) for c in chunks]}
    )

    try:
        for token in token_gen:
            yield format_sse({"type": "token", "text": token})
    except Exception as exc:  # LLM stream failure mid-flight
        logger.exception(f"chat token stream failed: {exc}")
        yield format_sse({"type": "error", **error_body("upstream_error", str(exc))})
        return

    yield format_sse({"type": "done"})


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

        sig = (status, task.get("progress"), task.get("message"))
        if sig != last_sig:
            yield format_sse({"type": "progress", "task": task})
            last_sig = sig

        if time.monotonic() > deadline:
            return
        time.sleep(TASK_STREAM_POLL_INTERVAL)
