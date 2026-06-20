"""The agentic chat agent — a Pydantic AI `Agent` plus its tools.

The agent is **model-less at construction**: the OpenRouter model is supplied at
run time (`run_stream(model=...)` / `dispatch_request(model=...)`), so importing
this module needs no API key and tests can inject a `TestModel`.

Tools are plain **synchronous** functions that wrap `merlin.services` / the
retriever; Pydantic AI runs them in a threadpool, so blocking SQLite I/O is
fine. Each tool catches its own errors and returns an informative string — a
tool never crashes the run. Tool results are **capped** before they enter the
model's context (transcript excerpts, bounded list lengths) to avoid the #1
agentic-chat regret: dumping big rows into history every turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic_ai import Agent, RunContext

from merlin.config import settings
from merlin.db.engine import get_db
from merlin.rag.prompts import AGENT_SYSTEM_PROMPT
from merlin.rag.retriever import HybridRetriever, RetrievedChunk
from merlin.services import library

_retriever = HybridRetriever()

# Caps that bound how much a single tool call can inject into context.
_MAX_SEARCH_LIMIT = 15
_MAX_BROWSE_LIMIT = 25
_TRANSCRIPT_EXCERPT_CHARS = 3000
_MAX_TAGS = 60


@dataclass
class ChatDeps:
    """Per-request dependencies for a chat run.

    `source_types` / `tags` are the chat-level FilterBar selections; they act as
    defaults a tool call may override. `cited` accumulates every item a tool
    surfaced this run, keyed by item id, for the consolidated "Sources" list.
    """

    source_types: list[str] | None = None
    tags: list[str] | None = None
    cited: dict[str, dict] = field(default_factory=dict)

    def cite(self, chunk: RetrievedChunk) -> None:
        """Record a retrieved chunk as a citation (first snippet wins)."""
        if chunk.knowledge_item_id not in self.cited:
            self.cited[chunk.knowledge_item_id] = {
                "item_id": chunk.knowledge_item_id,
                "title": chunk.title,
                "source_type": chunk.source_type,
                "snippet": chunk.excerpt,
                "score": chunk.score,
            }

    def cite_item(self, item: dict) -> None:
        """Record a `get_item` result as a citation."""
        item_id = item.get("id")
        if item_id and item_id not in self.cited:
            self.cited[item_id] = {
                "item_id": item_id,
                "title": item.get("title") or "Untitled",
                "source_type": item.get("source_type") or "",
                "snippet": (item.get("summary") or "")[:300],
                "score": 1.0,
            }


agent = Agent(deps_type=ChatDeps, system_prompt=AGENT_SYSTEM_PROMPT)

# The Reader's single-item chat: no tools (the transcript is supplied directly
# as per-run instructions by the service), so the model just answers from that
# one item. Same deps type so the route can build it uniformly; runs through the
# same VercelAIAdapter as the library-wide agent (see services/chat.py + §3a).
item_agent = Agent(deps_type=ChatDeps)

# A cheap one-shot agent that names a saved conversation from its first message,
# for the chat-history sidebar. Model-less at construction (like the others); the
# service injects the model at run time via `run_sync`.
TITLE_SYSTEM_PROMPT = (
    "You name conversations. Given the user's first message, reply with a short, "
    "specific title of at most 6 words that captures its topic. Output only the "
    "title — no quotes, no trailing punctuation, no 'Title:' prefix."
)
title_agent = Agent(system_prompt=TITLE_SYSTEM_PROMPT)


# --------------------------------------------------------------------------- #
# Per-turn search budget — graceful wind-down instead of a hard error.
#
# `run_step` is the 1-based index of the model request about to be made. Once the
# model has used `chat_max_requests` tool-calling steps, every tool starts
# *refusing* (returning a wrap-up instruction instead of doing work) and an
# instruction reinforces it, so a long, fruitless search ends with a real answer
# ("I couldn't find that in your library") instead of an UsageLimitExceeded
# error. We keep the tools registered (rather than withdrawing them) on purpose:
# some models emit raw tool-call markup as text when no tools are offered, which
# would leak into the answer. The route sets `request_limit` a few steps above
# `chat_max_requests` as a hard backstop and to give the model room to comply.
# --------------------------------------------------------------------------- #

_BUDGET_REFUSAL = (
    "Search budget for this turn is exhausted — do not call any more tools. "
    "Write your final answer NOW using only what you have already gathered. If "
    "your library doesn't actually cover the question, say so plainly; it's fine "
    "not to have found an answer. Do not guess or invent sources."
)


def _over_budget(ctx: RunContext[ChatDeps]) -> bool:
    # `run_step` is always present on a real RunContext; default 0 keeps the tools
    # callable from unit tests that pass a minimal ctx stand-in.
    return getattr(ctx, "run_step", 0) > settings.chat_max_requests


@agent.instructions
def budget_notice(ctx: RunContext[ChatDeps]) -> str:
    """Once over budget, tell the model to wrap up with what it has."""
    return _BUDGET_REFUSAL if _over_budget(ctx) else ""


@agent.tool
def search_library(
    ctx: RunContext[ChatDeps],
    query: str,
    source_types: list[str] | None = None,
    tags: list[str] | None = None,
    limit: int = 8,
) -> str:
    """Keyword-search the knowledge base and return the most relevant items.

    Pass a focused set of keywords (not a whole sentence). `source_types` and
    `tags` narrow the search; omit them to use the chat's active filters. Each
    result shows the item id, title, source, and a matching excerpt.
    """
    if _over_budget(ctx):
        return _BUDGET_REFUSAL
    try:
        limit = max(1, min(limit, _MAX_SEARCH_LIMIT))
        with get_db() as db:
            chunks = _retriever.retrieve(
                db,
                query=query,
                source_types=source_types or ctx.deps.source_types,
                tag_filters=tags or ctx.deps.tags,
                top_k=limit,
            )
        if not chunks:
            return f"No items in the library matched the search {query!r}."
        for c in chunks:
            ctx.deps.cite(c)
        return _format_chunks(chunks)
    except Exception as exc:  # never crash the run
        return f"search_library failed: {exc}"


@agent.tool
def get_item(ctx: RunContext[ChatDeps], item_id: str) -> str:
    """Read one item in depth: its summary plus an excerpt of its transcript.

    Use after `search_library`/`browse_library` when a specific item is clearly
    relevant and you need more than the search snippet.
    """
    if _over_budget(ctx):
        return _BUDGET_REFUSAL
    try:
        item = library.get_item(item_id)
        if item is None:
            return f"No item found with id {item_id!r}."
        ctx.deps.cite_item(item)
        return _format_item(item)
    except Exception as exc:
        return f"get_item failed: {exc}"


@agent.tool
def browse_library(
    ctx: RunContext[ChatDeps],
    source_type: str | None = None,
    tag: str | None = None,
    sort: str = "newest",
    limit: int = 15,
) -> str:
    """List items by filter (not keyword search) — for "what do I have about X",
    counting, or enumeration. Returns id + title + source + tags, newest first
    by default (`sort` may be "newest" or "oldest"). Also reports the total
    count matching the filter.
    """
    if _over_budget(ctx):
        return _BUDGET_REFUSAL
    try:
        limit = max(1, min(limit, _MAX_BROWSE_LIMIT))
        result = library.list_items(
            source_type=source_type or None,
            tags=[tag] if tag else (ctx.deps.tags or None),
            status="completed",
            sort=sort,
            per_page=limit,
        )
        items = result.get("items", [])
        total = result.get("total", len(items))
        if not items:
            return "No items match that filter."
        return _format_browse(items, total)
    except Exception as exc:
        return f"browse_library failed: {exc}"


@agent.tool
def list_tags(ctx: RunContext[ChatDeps]) -> str:
    """List the tags used across the library (the available topic vocabulary)."""
    if _over_budget(ctx):
        return _BUDGET_REFUSAL
    try:
        tags = library.list_tags()[:_MAX_TAGS]
        if not tags:
            return "The library has no tags yet."
        return ", ".join(f"{t['name']} ({t['count']})" for t in tags)
    except Exception as exc:
        return f"list_tags failed: {exc}"


@agent.tool
def list_source_types(ctx: RunContext[ChatDeps]) -> str:
    """List what kinds of content exist in the library, with counts."""
    if _over_budget(ctx):
        return _BUDGET_REFUSAL
    try:
        types = library.list_source_types()
        if not types:
            return "The library is empty."
        return ", ".join(f"{t['name']} ({t['count']})" for t in types)
    except Exception as exc:
        return f"list_source_types failed: {exc}"


# --------------------------------------------------------------------------- #
# Compact, capped formatting — keep tool output small (it enters history).
# --------------------------------------------------------------------------- #


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for c in chunks:
        head = f"[{c.knowledge_item_id}] {c.title}"
        if c.author:
            head += f" — {c.author}"
        head += f" ({c.source_type})"
        parts.append(f"{head}\n{c.excerpt}")
    return "\n\n".join(parts)


def _format_item(item: dict) -> str:
    lines = [
        f"id: {item.get('id')}",
        f"title: {item.get('title') or 'Untitled'}",
        f"source: {item.get('source_type')}",
    ]
    if item.get("channel") or item.get("author"):
        lines.append(f"author: {item.get('channel') or item.get('author')}")
    if item.get("tags"):
        lines.append(f"tags: {', '.join(item['tags'])}")
    if item.get("summary"):
        lines.append(f"\nSUMMARY:\n{item['summary']}")
    transcript = (item.get("raw_content") or "").strip()
    if transcript:
        excerpt = transcript[:_TRANSCRIPT_EXCERPT_CHARS]
        if len(transcript) > _TRANSCRIPT_EXCERPT_CHARS:
            excerpt += "\n…[transcript truncated]"
        lines.append(f"\nTRANSCRIPT EXCERPT:\n{excerpt}")
    return "\n".join(lines)


def _format_browse(items: list[dict], total: int) -> str:
    header = f"{total} item(s) match; showing {len(items)}:"
    rows = []
    for it in items:
        tags = ", ".join(it.get("tags") or [])
        row = f"[{it.get('id')}] {it.get('title') or 'Untitled'} ({it.get('source_type')})"  # noqa: E501
        if tags:
            row += f" — tags: {tags}"
        rows.append(row)
    return header + "\n" + "\n".join(rows)
