"""
POST /api/chat — RAG chat endpoint with Server-Sent Events streaming.

Payload:
    {
        "messages": [{"role": "user", "content": "..."}],
        "context_filters": {          // optional
            "source_types": ["youtube"],
            "tags": ["ai"]
        }
    }

SSE events:
    data: {"type": "chunk", "content": "..."}
    data: {"type": "citations", "sources": [...]}
    data: {"type": "done"}
    data: {"type": "error", "message": "..."}
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from backend.core.logging import logger
from backend.db.engine import get_db_session
from backend.rag.prompts import MERLIN_SYSTEM_PROMPT, format_context
from backend.rag.retriever import HybridRetriever

router = APIRouter(prefix="/chat", tags=["chat"])

retriever = HybridRetriever()


class ChatMessage(BaseModel):
    role: str    # "user" | "assistant" | "system"
    content: str


class ContextFilters(BaseModel):
    source_types: Optional[list[str]] = None
    tags: Optional[list[str]] = None


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    context_filters: Optional[ContextFilters] = None


@router.post("")
async def chat(body: ChatRequest, db: Session = Depends(get_db_session)):
    """Stream a RAG-augmented chat response as SSE."""

    def generate():
        try:
            # Extract user query (last user message)
            user_query = ""
            for msg in reversed(body.messages):
                if msg.role == "user":
                    user_query = msg.content
                    break

            if not user_query:
                yield _sse({"type": "error", "message": "No user message found"})
                return

            # Retrieve relevant chunks
            source_types = body.context_filters.source_types if body.context_filters else None
            tag_filters = body.context_filters.tags if body.context_filters else None

            chunks = retriever.retrieve(
                db,
                query=user_query,
                source_types=source_types,
                tag_filters=tag_filters,
                top_k=5,
            )

            context = format_context(chunks)

            # Build messages for the LLM
            system_msg = {"role": "system", "content": MERLIN_SYSTEM_PROMPT.format(context=context)}
            history = [{"role": m.role, "content": m.content} for m in body.messages[:-1]]
            current = {"role": "user", "content": user_query}
            llm_messages = [system_msg, *history, current]

            # Stream LLM response
            llm = settings.llm
            full_response = ""
            for chunk in llm.stream(llm_messages):
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                if content:
                    full_response += content
                    yield _sse({"type": "chunk", "content": content})

            # Yield citations
            citations = [
                {
                    "id": c.knowledge_item_id,
                    "title": c.title,
                    "source_type": c.source_type,
                    "author": c.author,
                }
                for c in chunks
            ]
            yield _sse({"type": "citations", "sources": citations})
            yield _sse({"type": "done"})

        except Exception as exc:
            logger.exception(f"Chat error: {exc}")
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"
