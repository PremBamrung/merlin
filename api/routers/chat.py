"""Chat endpoint — RAG over the knowledge base, streamed as SSE.

`POST /api/chat` returns an event stream (not `EventSource`, which can't POST a
body): citations first, then tokens, then `done`. See sse.chat_event_stream.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..schemas import ChatRequest
from ..sse import chat_event_stream

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
def chat(body: ChatRequest):
    history = [m.model_dump() for m in body.history]
    filters = body.filters.model_dump(exclude_none=True) if body.filters else {}
    return StreamingResponse(
        chat_event_stream(body.question, history, filters),
        media_type="text/event-stream",
    )
