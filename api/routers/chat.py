"""Chat endpoint — an agentic, tool-calling chat streamed in the Vercel AI SDK
data-stream protocol (consumed by `useChat` on the frontend).

`POST /api/chat` receives the AI SDK message list (plus our extra `filters`
field, which the request model tolerates) and drives a Pydantic AI agent through
`VercelAIAdapter`, which emits text / tool-call / tool-result / reasoning parts
as SSE. When `filters.item_id` is set the request is the Reader's single-item
chat: a tool-less agent grounded in that item's transcript (§3a).

The adapter handles framing, tool-delta assembly, the done sentinel, and
abort/disconnect; we own the proxy-buffering headers, the loop cap
(`UsageLimits`), and emitting the consolidated citations data-part.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui.vercel_ai.response_types import DataChunk
from pydantic_ai.usage import UsageLimits

from merlin.config import settings
from merlin.services import chat as chat_service

router = APIRouter(prefix="/api", tags=["chat"])

# Match the AI SDK v6 client; the adapter also supports v5.
_SDK_VERSION = 6

# Proxy/buffering headers so the SSE stream isn't buffered by an intermediary
# (nginx/Cloudflare) and reaches the browser token-by-token. Never GZip this.
_NO_BUFFER_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def _citations_emitter(deps: chat_service.ChatDeps):
    """on_complete hook: emit every item a tool touched as a `data-citations`
    part, for the frontend's consolidated "Sources" list."""

    async def on_complete(_result):
        if deps.cited:
            yield DataChunk(
                type="data-citations",
                data={"items": list(deps.cited.values())},
            )

    return on_complete


def _apply_stream_headers(response: Response) -> Response:
    for key, value in _NO_BUFFER_HEADERS.items():
        response.headers[key] = value
    return response


@router.post("/chat")
async def chat(request: Request) -> Response:
    # Read the body once (Starlette caches it, so the adapter re-reads for free)
    # to pull our extra `filters` field out of the AI SDK message payload.
    try:
        body = await request.json()
    except Exception:
        body = {}
    filters = (body or {}).get("filters") or {}
    item_id = filters.get("item_id")

    model = chat_service.build_chat_model()

    if item_id:
        # Reader single-item chat: tool-less agent, transcript as instructions.
        # ValueError (missing item) propagates to the 400 handler.
        instructions = chat_service.item_instructions(item_id)
        response = await VercelAIAdapter.dispatch_request(
            request,
            agent=chat_service.item_agent,
            deps=chat_service.ChatDeps(),
            model=model,
            instructions=instructions,
            # No tools → a single model request; keep a tiny margin.
            usage_limits=UsageLimits(request_limit=2),
            sdk_version=_SDK_VERSION,
        )
        return _apply_stream_headers(response)

    # Library-wide agentic chat.
    deps = chat_service.deps_from_filters(filters)
    response = await VercelAIAdapter.dispatch_request(
        request,
        agent=chat_service.agent,
        deps=deps,
        model=model,
        usage_limits=UsageLimits(request_limit=settings.chat_max_requests),
        on_complete=_citations_emitter(deps),
        sdk_version=_SDK_VERSION,
    )
    return _apply_stream_headers(response)
