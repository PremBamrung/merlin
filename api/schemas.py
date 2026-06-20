"""Pydantic request/response models — the source for the generated TS client.

These mirror the dicts the `merlin.services` serializers already produce
(`library.serialize_item`, `ingest._serialize_task`) so router responses stay
byte-compatible with FRONTEND_V3_API.md §2. Fields the service may omit/null
are given defaults; nothing here adds logic.

Note on loose scalar types: a few YouTube columns are stored as strings in the
DB (`duration` "HH:MM:SS", `subscribers`, `videos_count`) even though the API
doc shows them as ints. The serializer passes them through verbatim, so the
models accept either form rather than silently coercing.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #


class IngestYouTubeRequest(BaseModel):
    url: str
    languages: list[str] = Field(default_factory=lambda: ["en", "fr"])
    summary_length: str = "short"


class ResummarizeRequest(BaseModel):
    summary_length: str | None = None
    languages: list[str] | None = None


class RetryRequest(BaseModel):
    summary_length: str | None = None
    languages: list[str] | None = None


class UpdateItemRequest(BaseModel):
    tags: list[str] | None = None
    title: str | None = None


# Chat speaks the Vercel AI SDK data-stream protocol (the route reads the raw
# AI SDK message body via `Request`), so there is no ChatRequest model. These
# two document the *extra* `filters` field the client adds to that body and the
# shape of each item in the `data-citations` part the server emits — kept for
# reference and to mirror the frontend types (not wired into a route).
class ChatFilters(BaseModel):
    source_types: list[str] | None = None
    tags: list[str] | None = None
    # Scope the chat to a single item, using its full transcript (no RAG).
    item_id: str | None = None


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #


class ListItem(BaseModel):
    """A knowledge item as returned by list endpoints (no `raw_content`)."""

    id: str
    source_type: str
    source_id: str
    title: str | None = None
    author: str | None = None
    published_at: str | None = None
    ingested_at: str | None = None
    summary: str | None = None
    summary_length: str | None = None
    tags: list[str] = Field(default_factory=list)
    topics: dict = Field(default_factory=dict)
    llm_model: str | None = None
    word_count: int | None = None
    status: str | None = None
    error_message: str | None = None
    # Consumption state (Feed) — ISO timestamps; null = unread / not saved
    read_at: str | None = None
    saved_at: str | None = None
    # YouTube-specific — null for non-youtube sources
    channel: str | None = None
    views: int | None = None
    duration: int | str | None = None
    subscribers: int | str | None = None
    videos_count: int | str | None = None
    thumbnail_url: str | None = None
    detected_language: str | None = None
    description: str | None = None
    timestamps: dict = Field(default_factory=dict)


class Item(ListItem):
    """The detail shape (`GET /api/items/{id}`) — adds the full transcript."""

    raw_content: str | None = None


class ItemListResponse(BaseModel):
    items: list[ListItem]
    total: int
    page: int
    per_page: int


class Task(BaseModel):
    id: str
    task_type: str
    status: str
    progress: int = 0
    message: str | None = None
    error: str | None = None
    knowledge_item_id: str | None = None
    created_at: str | None = None
    result_data: dict | None = None


class TaskIdResponse(BaseModel):
    task_id: str


class Citation(BaseModel):
    item_id: str
    title: str
    source_type: str
    snippet: str
    score: float = 0.0


class NameCount(BaseModel):
    name: str
    count: int


class TimelinePoint(BaseModel):
    date: str
    count: int


class CountResponse(BaseModel):
    count: int


class HealthResponse(BaseModel):
    status: str
    source_types: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Inbox / Digest (Tier 1)
# --------------------------------------------------------------------------- #


class DigestActionRequest(BaseModel):
    action: str  # "keep" | "dismiss"


class InboxCounts(BaseModel):
    pending: int = 0
    processing: int = 0
    failed: int = 0
    reviewed: int = 0


class InboxResponse(BaseModel):
    pending: list[ListItem] = Field(default_factory=list)
    failed: list[Task] = Field(default_factory=list)
    counts: InboxCounts


class DigestActionResponse(BaseModel):
    item_id: str
    action: str


class RetryFailedResponse(BaseModel):
    task_ids: list[str] = Field(default_factory=list)


class ClearFailedResponse(BaseModel):
    cleared: int
