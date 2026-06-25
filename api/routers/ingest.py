"""Ingest + task endpoints — submit YouTube URLs, re-summarise, retry, and
inspect background tasks (incl. the SSE progress stream).

A *failed ingest task* is not an HTTP error: `POST /api/ingest/youtube` returns
`{task_id}` immediately and any failure surfaces later on the task row / SSE
`failed` event (FRONTEND_V3_API.md §5). Bad input (`ValueError`) → 400.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from merlin.services import ingest

from ..errors import not_found
from ..schemas import (
    CancelTaskResponse,
    IngestYouTubeRequest,
    IngestYouTubeResponse,
    ResummarizeRequest,
    RetryRequest,
    Task,
    TaskIdResponse,
)
from ..sse import task_progress_events

router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/ingest/youtube", response_model=IngestYouTubeResponse)
def ingest_youtube(body: IngestYouTubeRequest):
    # Server-side dedup happens inside the service: an already-ingested URL
    # returns {"status": "exists", item_id, title} instead of queueing, so the
    # client can confirm a re-summarise rather than redoing it silently.
    return ingest.submit_youtube(body.url, body.languages, body.summary_length)


@router.post("/items/{item_id}/resummarize", response_model=TaskIdResponse)
def resummarize(item_id: str, body: ResummarizeRequest | None = None):
    body = body or ResummarizeRequest()
    task_id = ingest.resummarize(item_id, body.summary_length, body.languages)
    return {"task_id": task_id}


@router.post("/items/{item_id}/retry", response_model=TaskIdResponse)
def retry(item_id: str, body: RetryRequest | None = None):
    body = body or RetryRequest()
    task_id = ingest.retry(item_id, body.languages, body.summary_length)
    return {"task_id": task_id}


@router.get("/tasks", response_model=list[Task])
def recent_tasks(limit: int = 10):
    return ingest.recent_tasks(limit)


@router.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: str):
    task = ingest.get_task(task_id)
    if task is None:
        raise not_found("Task not found.")
    return task


@router.post("/tasks/{task_id}/cancel", response_model=CancelTaskResponse)
def cancel_task(task_id: str):
    # 404 covers both unknown ids and already-terminal tasks (nothing to stop).
    if not ingest.cancel_task(task_id):
        raise not_found("Task not found or already finished.")
    return {"task_id": task_id, "status": "cancelling"}


@router.get("/tasks/{task_id}/stream")
def stream_task(task_id: str):
    return StreamingResponse(
        task_progress_events(task_id), media_type="text/event-stream"
    )
