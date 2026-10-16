"""The agentic chat agent — a Pydantic AI `Agent` plus its tools.

The agent is **model-less at construction**: the chat model is supplied at
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
from datetime import date, datetime, time

from pydantic_ai import Agent, RunContext
from pydantic_ai.tools import ToolDefinition

from merlin.config import settings
from merlin.core.logging import logger
from merlin.db.engine import get_db
from merlin.rag.prompts import AGENT_SYSTEM_PROMPT, WEB_SEARCH_GUIDANCE
from merlin.rag.retriever import HybridRetriever, RetrievedChunk
from merlin.services import library, topics

_retriever = HybridRetriever()

# Caps that bound how much a single tool call can inject into context.
_MAX_SEARCH_LIMIT = 15
_MAX_BROWSE_LIMIT = 25
_TRANSCRIPT_EXCERPT_CHARS = 3000
_MAX_TAGS = 60
_MAX_CHANNELS = 40
_MAX_GET_ITEMS = 6
_GET_ITEMS_SUMMARY_CHARS = 2500
# A date-sorted search reorders this many relevance hits (the rerank pool size).
_SORT_POOL = 20
_SEARCH_SORTS = ("relevance", "newest", "oldest")
_BROWSE_SORTS = ("newest", "oldest", "relevance")
_WEB_ANSWER_CHARS = 4000
_MAX_WEB_SOURCES = 8
_WEB_SEARCH_TIMEOUT = 60.0
# Vertex returns opaque redirect links for grounding sources; each is resolved to
# the real page with one HEAD request (302 → Location) so the model cites it.
_GROUNDING_REDIRECT = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/"
_REDIRECT_TIMEOUT = 3.0


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
def current_date() -> str:
    """Give the model today's date for recency / relative-time reasoning.

    Lives in `@agent.instructions` (not the static system prompt) so it is
    recomputed once per run and never persisted into message history — each turn
    gets the current date, with no stale copies accumulating across a long
    conversation. Attached only to the library-wide `agent`; the Reader's
    `item_agent` answers from one fixed item and has no use for "now".
    """
    return (
        f"Today's date is {date.today().isoformat()}. Use it for recency and "
        'relative-time reasoning (e.g. "most recent in the library", "the last '
        'month", "N days after release"). Each item\'s own publication date '
        "appears in tool results."
    )


@agent.instructions
def budget_notice(ctx: RunContext[ChatDeps]) -> str:
    """Once over budget, tell the model to wrap up with what it has."""
    return _BUDGET_REFUSAL if _over_budget(ctx) else ""


@agent.instructions
def web_search_notice() -> str:
    """Tell the model when to reach for `web_search` — only when it's offered."""
    return WEB_SEARCH_GUIDANCE if settings.is_litellm else ""


@agent.tool
def search_library(
    ctx: RunContext[ChatDeps],
    query: str,
    source_types: list[str] | None = None,
    tags: list[str] | None = None,
    sort: str = "relevance",
    after: str | None = None,
    before: str | None = None,
    limit: int = 8,
) -> str:
    """Search the knowledge base and return the most relevant items.

    Search is **hybrid**: it fuses keyword (full-text) matching with semantic
    (meaning-based) matching, so a natural phrase works as well as bare
    keywords — phrase the `query` the way you'd describe what you're looking
    for, and don't strip it down to lone keywords. `source_types` and `tags`
    narrow the search; omit them to use the chat's active filters. `after` /
    `before` (YYYY-MM-DD, inclusive) bound the publication date. `sort` is
    "relevance" (default), or "newest" / "oldest" to order the most relevant
    hits by publication date — use it for "latest on X"; for *everything*
    matching a keyword in date order, use `browse_library(search=...)`. Each
    result shows the item id, title, author, publication date, tags and a
    matching excerpt; a header reports the total match count when more exist
    than shown. Don't put creator names in `query` to find their videos — use
    `browse_library(channel=...)`.
    """
    if _over_budget(ctx):
        return _BUDGET_REFUSAL
    try:
        if sort not in _SEARCH_SORTS:
            return f"Invalid sort {sort!r}; use one of: {', '.join(_SEARCH_SORTS)}."
        after_d, before_d = _parse_date(after), _parse_date(before)
        limit = max(1, min(limit, _MAX_SEARCH_LIMIT))
        eff_source_types = source_types or ctx.deps.source_types
        eff_tags = library.normalize_tags(tags or ctx.deps.tags or []) or None
        bounds = {"after": after_d, "before": before_d}
        # A date sort reorders a full relevance pool, so the newest *relevant*
        # items surface even when they ranked below the top `limit`.
        top_k = limit if sort == "relevance" else max(limit, _SORT_POOL)
        with get_db() as db:
            chunks = _retriever.retrieve(
                db,
                query=query,
                source_types=eff_source_types,
                tag_filters=eff_tags,
                top_k=top_k,
                **bounds,
            )
            # Exact total is meaningful only without post-hoc tag filtering
            # (count() reflects MATCH + source_type, not the JSON tag filter).
            total = (
                None
                if eff_tags
                else _retriever.count(db, query, eff_source_types, **bounds)
            )
        if not chunks:
            return f"No items in the library matched the search {query!r}."
        if sort != "relevance":
            chunks = _sort_by_date(chunks, newest=sort == "newest")[:limit]
        for c in chunks:
            ctx.deps.cite(c)
        return _format_chunks(chunks, total)
    except ValueError as exc:
        return str(exc)
    except Exception as exc:  # never crash the run
        return f"search_library failed: {exc}"


@agent.tool
def get_item(
    ctx: RunContext[ChatDeps], item_id: str, transcript_offset: int = 0
) -> str:
    """Read one item in depth: its summary plus an excerpt of its transcript.

    Use when you need detail beyond the summary. To read several items'
    summaries, use `get_items` in one call instead. The transcript is shown in
    windows; if it ends with a "chars remain" note, call this again with
    `transcript_offset` set to the value it suggests to read the next window —
    or use `search_transcript` to jump straight to the relevant passage.
    """
    if _over_budget(ctx):
        return _BUDGET_REFUSAL
    try:
        item = library.get_item(item_id)
        if item is None:
            return f"No item found with id {item_id!r}."
        ctx.deps.cite_item(item)
        return _format_item(item, offset=transcript_offset)
    except Exception as exc:
        return f"get_item failed: {exc}"


@agent.tool
def get_items(ctx: RunContext[ChatDeps], item_ids: list[str]) -> str:
    """Read the summaries of several items at once (up to 6 per call).

    The default way to read what you found: pass every relevant id from your
    searches in ONE call rather than calling `get_item` repeatedly. Returns each
    item's metadata, tags and summary — no transcript (use `get_item` or
    `search_transcript` for transcript detail on a specific item).
    """
    if _over_budget(ctx):
        return _BUDGET_REFUSAL
    try:
        ids = list(dict.fromkeys(i for i in item_ids if i))
        if not ids:
            return "No item ids given."
        dropped = ids[_MAX_GET_ITEMS:]
        parts = []
        for item_id in ids[:_MAX_GET_ITEMS]:
            item = library.get_item(item_id)
            if item is None:
                parts.append(f"id: {item_id}\n(no item found with this id)")
                continue
            ctx.deps.cite_item(item)
            parts.append(_format_item_summary(item))
        out = "\n\n---\n\n".join(parts)
        if dropped:
            out += (
                f"\n\n[{len(dropped)} more id(s) not read — at most "
                f"{_MAX_GET_ITEMS} per call: {', '.join(dropped)}]"
            )
        return out
    except Exception as exc:
        return f"get_items failed: {exc}"


@agent.tool
def search_transcript(ctx: RunContext[ChatDeps], item_id: str, query: str) -> str:
    """Find the passages of ONE item's transcript that discuss `query`.

    Use when an item's summary doesn't cover a specific point you need —
    instead of paging through the transcript window by window. Returns the
    best-matching passages with their transcript offsets; call
    `get_item(item_id, transcript_offset=...)` to read on from one.
    """
    if _over_budget(ctx):
        return _BUDGET_REFUSAL
    try:
        result = library.search_transcript(item_id, query)
        if result is None:
            return f"No item found with id {item_id!r}."
        if not result["length"]:
            return f"{result['title']!r} has no transcript to search."
        if not result["hits"]:
            return f"No passage in {result['title']!r}'s transcript mentions {query!r}."
        ctx.deps.cite_item(
            {
                "id": item_id,
                "title": result["title"],
                "source_type": result["source_type"],
            }
        )
        return _format_transcript_hits(item_id, result)
    except Exception as exc:
        return f"search_transcript failed: {exc}"


@agent.tool
def browse_library(
    ctx: RunContext[ChatDeps],
    source_type: str | None = None,
    tag: str | None = None,
    channel: str | None = None,
    topic: str | None = None,
    search: str | None = None,
    sort: str = "newest",
    after: str | None = None,
    before: str | None = None,
    limit: int = 15,
) -> str:
    """List items by filter (not semantic search) — for "what do I have about
    X", "everything by <creator>", counting, or enumeration.

    Filters combine: `channel` (a creator/channel name — see `list_channels`),
    `topic` (a topic slug — see `list_topics`), `tag`, `source_type`, `search`
    (keyword match on title/summary/tags), and `after` / `before` (YYYY-MM-DD,
    inclusive, on publication date). `sort` is "newest" (default) or "oldest"
    by date *added to the library*, or "relevance" when `search` is set.
    Returns id + title + channel + date + tags, plus the total count matching.
    """
    if _over_budget(ctx):
        return _BUDGET_REFUSAL
    try:
        if sort not in _BROWSE_SORTS:
            return f"Invalid sort {sort!r}; use one of: {', '.join(_BROWSE_SORTS)}."
        after_d, before_d = _parse_date(after), _parse_date(before)
        limit = max(1, min(limit, _MAX_BROWSE_LIMIT))
        result = library.list_items(
            source_type=source_type or None,
            tags=[tag] if tag else (ctx.deps.tags or None),
            channel=channel or None,
            topics=[topic] if topic else None,
            search=search or None,
            status="completed",
            sort=sort,
            per_page=limit,
            published_after=(
                datetime.combine(date.fromisoformat(after_d), time.min)
                if after_d
                else None
            ),
            published_before=(
                datetime.combine(date.fromisoformat(before_d), time.max)
                if before_d
                else None
            ),
        )
        items = result.get("items", [])
        total = result.get("total", len(items))
        if not items:
            return "No items match that filter."
        return _format_browse(items, total)
    except ValueError as exc:
        return str(exc)
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


@agent.tool
def list_topics(ctx: RunContext[ChatDeps]) -> str:
    """List the library's curated topics (its subject areas) with item counts.

    Topics are broader and cleaner than tags — the best entry point for "catch
    me up on <subject>". Pass a topic's slug to `browse_library(topic=...)`.
    """
    if _over_budget(ctx):
        return _BUDGET_REFUSAL
    try:
        found = topics.list_topics()
        if not found:
            return "The library has no topics yet."
        return "\n".join(f"{t['slug']}: {t['label']} ({t['count']})" for t in found)
    except Exception as exc:
        return f"list_topics failed: {exc}"


@agent.tool
def list_channels(ctx: RunContext[ChatDeps]) -> str:
    """List the creators/channels in the library, most items first.

    Pass a name to `browse_library(channel=...)` to list exactly that creator's
    items (far more precise than putting their name in a search query).
    """
    if _over_budget(ctx):
        return _BUDGET_REFUSAL
    try:
        channels = library.top_channels(limit=_MAX_CHANNELS)
        if not channels:
            return "The library has no channels yet."
        return ", ".join(f"{c['name']} ({c['count']})" for c in channels)
    except Exception as exc:
        return f"list_channels failed: {exc}"


# --------------------------------------------------------------------------- #
# Web search (LiteLLM only). A separate sub-call to a Google-Search-grounded
# proxy alias rather than grounding the chat model itself: Vertex has
# historically restricted combining grounding with custom function tools in one
# request. Web results are cited as markdown links in the answer; they never
# enter `ctx.deps.cited` (the Sources panel stays library-only).
# --------------------------------------------------------------------------- #


def _only_on_litellm(
    ctx: RunContext[ChatDeps], tool_def: ToolDefinition
) -> ToolDefinition | None:
    """Offer the tool only when the LiteLLM proxy is the provider."""
    return tool_def if settings.is_litellm else None


_web_client = None


def _web_search_client():
    """The OpenAI-compatible client for the proxy (built on first use)."""
    global _web_client
    if _web_client is None:
        from openai import OpenAI

        _web_client = OpenAI(
            base_url=settings.litellm_base_url,
            api_key=settings.litellm_api_key or "litellm-placeholder",
            timeout=_WEB_SEARCH_TIMEOUT,
        )
    return _web_client


@agent.tool(prepare=_only_on_litellm)
def web_search(ctx: RunContext[ChatDeps], query: str) -> str:
    """Search the public web and return a short answer with its source links.

    For current events or anything outside the user's library. Phrase `query`
    as a full question. Cite what you use as markdown links to the listed URLs.
    """
    if _over_budget(ctx):
        return _BUDGET_REFUSAL
    try:
        resp = _web_search_client().chat.completions.create(
            model=settings.litellm_web_search_model,
            messages=[{"role": "user", "content": query}],
        )
        answer = (resp.choices[0].message.content or "").strip()
        if not answer:
            return f"The web search for {query!r} returned nothing."
        return _format_web(answer, _web_sources(resp))
    except Exception as exc:  # never crash the run
        logger.warning("web_search failed", exc_info=True)
        return f"web_search failed: {exc}"


def _web_sources(resp) -> list[tuple[str, str]]:
    """(title, url) pairs from LiteLLM's Vertex grounding metadata.

    LiteLLM passes Vertex's metadata through as a non-standard
    `vertex_ai_grounding_metadata` field (one entry per candidate), on the
    response or its message. Best-effort: an unexpected shape yields no sources,
    never an error.
    """
    meta = None
    for obj in (resp, getattr(resp.choices[0], "message", None)):
        extra = getattr(obj, "model_extra", None) or {}
        meta = extra.get("vertex_ai_grounding_metadata") or meta
    if isinstance(meta, dict):
        meta = [meta]
    sources: list[tuple[str, str]] = []
    for entry in meta or []:
        chunks = entry.get("groundingChunks") if isinstance(entry, dict) else None
        for chunk in chunks or []:
            web = (chunk or {}).get("web") or {}
            url = web.get("uri")
            if url and url not in (u for _, u in sources):
                sources.append((web.get("title") or url, url))
    sources = sources[:_MAX_WEB_SOURCES]
    if not sources:
        return sources
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        resolved = list(pool.map(_resolve_redirect, (u for _, u in sources)))
    # Distinct redirect links can land on the same page — keep the first.
    out: list[tuple[str, str]] = []
    for (title, _), url in zip(sources, resolved, strict=True):
        if url not in (u for _, u in out):
            out.append((title, url))
    return out


def _resolve_redirect(url: str) -> str:
    """The page a Vertex grounding redirect points at, or `url` unchanged when
    it isn't one or can't be resolved (the redirect link still works for a
    while, so it beats dropping the source)."""
    if not url.startswith(_GROUNDING_REDIRECT):
        return url
    try:
        import requests

        resp = requests.head(url, allow_redirects=False, timeout=_REDIRECT_TIMEOUT)
        location = resp.headers.get("Location")
        if resp.is_redirect and location and location.startswith("http"):
            return location
    except Exception:
        logger.debug("Could not resolve grounding redirect", exc_info=True)
    return url


# --------------------------------------------------------------------------- #
# Compact, capped formatting — keep tool output small (it enters history).
# --------------------------------------------------------------------------- #


def _parse_date(value: str | None) -> str | None:
    """Validate a YYYY-MM-DD tool argument; None passes through. Raises a
    ValueError whose message is returned to the model as the tool result."""
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        raise ValueError(f"Invalid date {value!r}; use YYYY-MM-DD.") from None


def _sort_by_date(chunks: list[RetrievedChunk], newest: bool) -> list[RetrievedChunk]:
    """Order by publication date (newest or oldest first), undated last."""
    dated = sorted(
        (c for c in chunks if c.published_at),
        key=lambda c: c.published_at,
        reverse=newest,
    )
    return dated + [c for c in chunks if not c.published_at]


def _format_chunks(chunks: list[RetrievedChunk], total: int | None = None) -> str:
    parts = []
    for c in chunks:
        head = f"[{c.knowledge_item_id}] {c.title}"
        if c.author:
            head += f" — {c.author}"
        head += f" ({c.source_type})"
        if c.published_at:
            head += f" · {c.published_at}"
        if c.tags:
            head += f"\ntags: {', '.join(c.tags)}"
        parts.append(f"{head}\n{c.excerpt}")
    body = "\n\n".join(parts)
    # Coverage signal: only when there's more than what's shown.
    if total is not None and total > len(chunks):
        return f"{total} matches; showing top {len(chunks)}:\n\n{body}"
    return body


def _meta_lines(item: dict) -> list[str]:
    """The metadata header shared by `get_item` and `get_items`."""
    lines = [
        f"id: {item.get('id')}",
        f"title: {item.get('title') or 'Untitled'}",
        f"source: {item.get('source_type')}",
    ]
    if item.get("channel") or item.get("author"):
        lines.append(f"author: {item.get('channel') or item.get('author')}")
    if item.get("published_at"):
        lines.append(f"published: {item['published_at'][:10]}")
    if item.get("duration"):
        lines.append(f"duration: {item['duration']}")
    if item.get("views"):
        lines.append(f"views: {item['views']:,}")
    if item.get("tags"):
        lines.append(f"tags: {', '.join(item['tags'])}")
    return lines


def _format_item(item: dict, offset: int = 0) -> str:
    lines = _meta_lines(item)
    if item.get("summary"):
        lines.append(f"\nSUMMARY:\n{item['summary']}")
    transcript = (item.get("raw_content") or "").strip()
    if transcript:
        start = max(0, offset)
        window = transcript[start : start + _TRANSCRIPT_EXCERPT_CHARS]
        end = start + len(window)
        prefix = "…[continued]\n" if start > 0 else ""
        suffix = ""
        if end < len(transcript):
            suffix = (
                f"\n…[{len(transcript) - end} chars remain — call "
                f"get_item(item_id, transcript_offset={end}) to continue]"
            )
        lines.append(f"\nTRANSCRIPT EXCERPT:\n{prefix}{window}{suffix}")
    return "\n".join(lines)


def _format_item_summary(item: dict) -> str:
    """One `get_items` entry: metadata + (capped) summary, never the transcript."""
    lines = _meta_lines(item)
    summary = (item.get("summary") or "").strip()
    if len(summary) > _GET_ITEMS_SUMMARY_CHARS:
        summary = (
            summary[:_GET_ITEMS_SUMMARY_CHARS]
            + "…[summary truncated — get_item for the full summary]"
        )
    lines.append(f"SUMMARY:\n{summary}" if summary else "(no summary)")
    transcript_len = len((item.get("raw_content") or "").strip())
    if transcript_len:
        lines.append(
            f"[transcript: {transcript_len:,} chars — read with get_item or "
            "search_transcript]"
        )
    return "\n".join(lines)


def _format_transcript_hits(item_id: str, result: dict) -> str:
    hits = result["hits"]
    parts = [
        f"{len(hits)} passage(s) from {result['title']!r} "
        f"(transcript: {result['length']:,} chars):"
    ]
    for h in hits:
        parts.append(f"@offset {h['offset']:,}:\n…{h['text']}…")
    parts.append(
        f"[read on from a passage with get_item({item_id!r}, "
        "transcript_offset=<offset>)]"
    )
    return "\n\n".join(parts)


def _format_browse(items: list[dict], total: int) -> str:
    header = f"{total} item(s) match; showing {len(items)}:"
    rows = []
    for it in items:
        tags = ", ".join(it.get("tags") or [])
        row = f"[{it.get('id')}] {it.get('title') or 'Untitled'} ({it.get('source_type')})"  # noqa: E501
        if it.get("channel") or it.get("author"):
            row += f" — {it.get('channel') or it.get('author')}"
        if it.get("published_at"):
            row += f" · {it['published_at'][:10]}"
        if tags:
            row += f" — tags: {tags}"
        rows.append(row)
    return header + "\n" + "\n".join(rows)


def _format_web(answer: str, sources: list[tuple[str, str]]) -> str:
    if len(answer) > _WEB_ANSWER_CHARS:
        answer = answer[:_WEB_ANSWER_CHARS] + "…[truncated]"
    if not sources:
        return f"WEB ANSWER (no source links returned):\n{answer}"
    links = "\n".join(f"- {title}: {url}" for title, url in sources)
    return f"WEB ANSWER:\n{answer}\n\nWEB SOURCES:\n{links}"
