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

import re

from fastapi import APIRouter, BackgroundTasks, Request, Response
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui.vercel_ai.response_types import DataChunk
from pydantic_ai.usage import UsageLimits

from merlin.config import settings
from merlin.services import chat as chat_service, chat_history

from ..errors import not_found
from ..schemas import (
    ChatThreadDetail,
    ChatThreadSummary,
    RenameThreadRequest,
    SaveThreadRequest,
    SaveThreadResponse,
)

router = APIRouter(prefix="/api", tags=["chat"])

# Match the AI SDK v6 client; the adapter also supports v5.
_SDK_VERSION = 6

# Extra model-requests allowed beyond `chat_max_requests` for the agent to emit
# its final answer after the tools start refusing (see merlin.rag.agent). Keeps
# the graceful wind-down from being cut off by the hard `request_limit`.
_BUDGET_GRACE = 3

# Proxy/buffering headers so the SSE stream isn't buffered by an intermediary
# (nginx/Cloudflare) and reaches the browser token-by-token. Never GZip this.
_NO_BUFFER_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


# Inline citation markers the model emits, e.g. `[#a1b2c3d4]` — but models often
# drop the `#` and mirror the bracketed id shown in tool output (`[a1b2c3d4]`),
# so the `#` is optional. Require 8+ hex/dash chars (a UUID or its prefix) so
# ordinary prose brackets (`[1]`, footnotes) never match.
_MARKER_RE = re.compile(r"\[#?([0-9a-fA-F-]{8,})\]")


def _resolve_marker(marker: str, viewed: dict[str, dict]) -> str | None:
    """Map a marker id to a viewed item id, tolerating abbreviation.

    Models routinely shorten UUIDs (they emit `[#98aa2fbb]` for the full id
    `98aa2fbb-…`), so fall back from an exact hit to a **unique** prefix match.
    Ambiguous prefixes (matching >1 viewed item) are dropped — better to miss a
    citation than mis-attribute one.
    """
    marker = marker.lower()
    if marker in viewed:
        return marker
    hits = [iid for iid in viewed if iid.lower().startswith(marker)]
    return hits[0] if len(hits) == 1 else None


def _citations_emitter(deps: chat_service.ChatDeps):
    """on_complete hook: split the items a tool surfaced into **used** vs merely
    **viewed**, and emit them as two data-parts for the frontend's "Sources" /
    "Also searched" tiers.

    "Used" is derived from the final answer text: the items the model tagged
    with an inline `[#id]` marker. Two graceful fallbacks keep the Sources list
    sensible when the model ignores markers — match item titles appearing in the
    text, then (last resort) treat every viewed item as used, so a clearly
    grounded answer never shows an empty Sources list.
    """

    async def on_complete(result):
        viewed = deps.cited  # {item_id: citation}
        if not viewed:
            return

        text = getattr(result, "output", "") or ""

        # Primary signal: explicit [#id] markers, resolved against what tools
        # actually surfaced (drops hallucinated ids, tolerates abbreviation).
        used_ids = {
            resolved
            for m in _MARKER_RE.findall(text)
            if (resolved := _resolve_marker(m, viewed))
        }

        # Fallback 1: no markers → items whose title appears verbatim in the text.
        if not used_ids:
            lowered = text.lower()
            used_ids = {
                iid
                for iid, c in viewed.items()
                if c.get("title") and c["title"].lower() in lowered
            }

        # Fallback 2: still nothing → treat all viewed as used (never empty).
        if not used_ids:
            used_ids = set(viewed)

        used = [c for iid, c in viewed.items() if iid in used_ids]
        also = [c for iid, c in viewed.items() if iid not in used_ids]

        if used:
            yield DataChunk(type="data-citations", data={"items": used})
        if also:
            yield DataChunk(type="data-sources-viewed", data={"items": also})

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

    # Library-wide agentic chat. Once the agent spends its `chat_max_requests`
    # search budget the tools start refusing and the agent is told to answer from
    # what it has (see merlin.rag.agent), so a long search ends with a graceful
    # answer. `request_limit` sits a few steps above the budget: a hard backstop
    # that also gives the model room to produce that final answer.
    deps = chat_service.deps_from_filters(filters)
    response = await VercelAIAdapter.dispatch_request(
        request,
        agent=chat_service.agent,
        deps=deps,
        model=model,
        usage_limits=UsageLimits(
            request_limit=settings.chat_max_requests + _BUDGET_GRACE
        ),
        on_complete=_citations_emitter(deps),
        sdk_version=_SDK_VERSION,
    )
    return _apply_stream_headers(response)


# --------------------------------------------------------------------------- #
# Chat history — continuable threads (library-wide chat only). The Reader's
# per-item chat is ephemeral and never hits these. Persistence is client-driven:
# the browser PUTs the full message list at the end of each turn (it holds the
# exact rendered parts, citations included). See services/chat_history.py.
# --------------------------------------------------------------------------- #


@router.get("/chat/threads", response_model=list[ChatThreadSummary])
def list_chat_threads():
    return chat_history.list_threads()


@router.get("/chat/threads/{thread_id}", response_model=ChatThreadDetail)
def get_chat_thread(thread_id: str):
    thread = chat_history.get_thread(thread_id)
    if thread is None:
        raise not_found("Conversation not found.")
    return thread


@router.put("/chat/threads/{thread_id}", response_model=SaveThreadResponse)
def save_chat_thread(
    thread_id: str, body: SaveThreadRequest, background_tasks: BackgroundTasks
):
    result = chat_history.save_thread(
        thread_id,
        [m.model_dump() for m in body.messages],
        title=body.title,
    )
    # Title generation is a slow LLM call — run it after the response is sent so
    # the save returns immediately; the title shows up on a later sidebar refetch.
    if result.pop("needs_title", False):
        background_tasks.add_task(
            chat_history.generate_and_store_title, thread_id
        )
    return result


@router.patch("/chat/threads/{thread_id}", response_model=SaveThreadResponse)
def rename_chat_thread(thread_id: str, body: RenameThreadRequest):
    if not chat_history.rename_thread(thread_id, body.title):
        raise not_found("Conversation not found.")
    return {"id": thread_id, "title": body.title}


@router.delete("/chat/threads/{thread_id}", status_code=204)
def delete_chat_thread(thread_id: str):
    if not chat_history.delete_thread(thread_id):
        raise not_found("Conversation not found.")
    return Response(status_code=204)
