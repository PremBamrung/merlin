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

from typing import Literal

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


class RefetchRequest(BaseModel):
    summary_length: str | None = None
    languages: list[str] | None = None


class UpdateItemRequest(BaseModel):
    tags: list[str] | None = None
    title: str | None = None


# --- Topics (cross-corpus taxonomy) ----------------------------------------


class CreateTopicRequest(BaseModel):
    label: str
    description: str | None = None


class PatchTopicRequest(BaseModel):
    """Rename, archive, or merge a topic — mutually exclusive in practice."""

    label: str | None = None
    archive: bool | None = None
    merge_into: str | None = None  # topic id to fold this one into


class SetItemTopicsRequest(BaseModel):
    """Manual assignment: the full topic set for an item + which is primary."""

    topic_ids: list[str] = Field(default_factory=list)
    primary_id: str | None = None


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


# Chat-history (continuable threads). A message's `parts` are the Vercel AI SDK
# `UIMessage` parts stored verbatim (arbitrary shapes per part type), so they're
# modelled loosely as a list of dicts rather than a discriminated union.
class ChatMessageModel(BaseModel):
    id: str | None = None
    role: str
    parts: list[dict] = Field(default_factory=list)


class SaveThreadRequest(BaseModel):
    """Client-driven persistence: the full ordered message list for the thread."""

    messages: list[ChatMessageModel] = Field(default_factory=list)
    # Optional explicit title (e.g. a rename folded into a save); when omitted the
    # server generates one on the first turn.
    title: str | None = None


class RenameThreadRequest(BaseModel):
    title: str


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #


class ItemTopicRef(BaseModel):
    """A topic assigned to an item, as it appears on the item payload."""

    slug: str
    label: str
    is_primary: bool = False


class TopicItem(BaseModel):
    """A topic row with its assigned-item count (list/manage responses)."""

    id: str
    slug: str
    label: str
    status: str = "active"
    origin: str = "user"
    description: str | None = None
    count: int = 0


class TopicCard(TopicItem):
    """A topic on the Topics overview: its share, what's new, a preview."""

    # Unread items ingested since the client's last visit.
    new_count: int = 0
    share: float = 0.0
    top_tags: list[str] = Field(default_factory=list)
    preview: list[ListItem] = Field(default_factory=list)


class TopicOverviewResponse(BaseModel):
    total: int
    topics: list[TopicCard]


class TopicDetailResponse(TopicItem):
    """One topic's page header: size, share, hours, channels, sub-tags."""

    share: float = 0.0
    seconds: int = 0
    channel_count: int = 0
    new_count: int = 0
    tags: list[NameCount] = Field(default_factory=list)
    channels: list[NameCount] = Field(default_factory=list)


class ItemTopicsResponse(BaseModel):
    item_id: str
    topics: list[ItemTopicRef] = Field(default_factory=list)


# --- Topic proposals (batch discovery pipeline, §7) ------------------------


class ProposalMemberItem(BaseModel):
    id: str
    title: str | None = None
    # Card fields, for the examples in the review queue.
    thumbnail_url: str | None = None
    channel: str | None = None
    duration: int | str | None = None
    source_id: str | None = None


class TopicProposalResponse(BaseModel):
    id: str
    proposed_label: str
    rationale: str | None = None
    batch_id: str | None = None
    created_at: str | None = None
    item_count: int = 0
    items: list[ProposalMemberItem] = Field(default_factory=list)


class AcceptProposalRequest(BaseModel):
    """Accept a proposal: create a new topic (`label`) OR merge its members into
    an existing one (`topic_id`). Both optional — omit to use the proposed label."""

    label: str | None = None
    topic_id: str | None = None


class AcceptProposalResponse(BaseModel):
    topic: TopicItem
    assigned: int  # members actually assigned (drift-tolerant)
    requested: int  # members in the proposal snapshot


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
    # Cross-corpus taxonomy assignments (navigation). Primary-first.
    topics: list[ItemTopicRef] = Field(default_factory=list)
    # Per-item in-summary section map {"heading": "12:34"} (was `topics`).
    sections: dict = Field(default_factory=dict)
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
    # Provenance of the summarised text — null on items ingested before it was
    # recorded. transcript_source: manual | auto | audio.
    transcript_language: str | None = None
    transcript_source: str | None = None
    summary_language: str | None = None
    description: str | None = None
    timestamps: dict = Field(default_factory=dict)


class IngestUsage(BaseModel):
    """What building one item cost: the latest summary's tokens + total spend."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    audio_seconds: float | None = None
    runs: int = 0


class Item(ListItem):
    """The detail shape (`GET /api/items/{id}`) — adds the full transcript and
    the item's ingest usage (null when nothing was recorded)."""

    raw_content: str | None = None
    ingest_usage: IngestUsage | None = None


class ItemListResponse(BaseModel):
    items: list[ListItem]
    total: int
    page: int
    per_page: int


class SearchHit(ListItem):
    """A Library item found by unified search, with why it matched."""

    excerpt: str = ""
    score: float = 0.0
    # Which retrieval arm found it: keyword (fts), meaning (vector) or both.
    match: Literal["fts", "vector", "both"] = "fts"


class SearchResponse(BaseModel):
    query: str
    items: list[SearchHit]


class Task(BaseModel):
    id: str
    task_type: str
    status: str
    progress: int = 0
    message: str | None = None
    title: str | None = None
    source_input: str | None = None
    error: str | None = None
    knowledge_item_id: str | None = None
    created_at: str | None = None
    result_data: dict | None = None


class TaskIdResponse(BaseModel):
    task_id: str


class IngestYouTubeResponse(BaseModel):
    """Either an ingest was started, or the video is already in the library.

    `status == "started"` → `task_id` is set (poll it). `status == "exists"` →
    nothing was queued; `item_id`/`title` identify the existing item so the
    client can confirm with the user before re-summarising.
    """

    status: str = "started"  # "started" | "exists"
    task_id: str | None = None
    item_id: str | None = None
    title: str | None = None


class CancelTaskResponse(BaseModel):
    task_id: str
    status: str = "cancelling"


class Citation(BaseModel):
    item_id: str
    title: str
    source_type: str
    snippet: str
    score: float = 0.0


class ChatThreadSummary(BaseModel):
    """A row in the chat-history sidebar."""

    id: str
    title: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    message_count: int = 0
    # First user message, shown when `title` is still NULL.
    preview: str | None = None


class HomeThread(ChatThreadSummary):
    """The conversation to pick up, with the tail of its last answer."""

    last_reply: str | None = None
    source_count: int = 0


class HomeTopic(BaseModel):
    slug: str
    label: str
    count: int
    # "new": most items since the last visit; "unread": none were new, so the
    # topic with the most unread items instead.
    kind: Literal["new", "unread"]


class HomeResponse(BaseModel):
    """The chat-first home's "since last time" digest (GET /api/home)."""

    since: str
    unread_count: int
    new_since_count: int
    strip: list[ListItem]
    strip_kind: Literal["new", "unread"]
    continue_thread: HomeThread | None = None
    busy_topic: HomeTopic | None = None
    saved_revisit: ListItem | None = None


class ChatThreadDetail(BaseModel):
    id: str
    title: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    messages: list[ChatMessageModel] = Field(default_factory=list)


class SaveThreadResponse(BaseModel):
    id: str
    title: str | None = None


class NameCount(BaseModel):
    name: str
    count: int


class TimelinePoint(BaseModel):
    date: str
    count: int


class CountResponse(BaseModel):
    count: int


# --- Usage / cost (Insights spend; visibility only) -------------------------


class UsageTotal(BaseModel):
    tokens_in: int
    tokens_out: int
    cost_usd: float
    calls: int


class UsageDayPoint(BaseModel):
    date: str
    surface: str
    cost_usd: float


class UsageSurface(BaseModel):
    surface: str
    cost_usd: float
    calls: int


class UsageModel(BaseModel):
    model: str
    cost_usd: float
    calls: int


class UsageResponse(BaseModel):
    total: UsageTotal
    by_day: list[UsageDayPoint]
    by_surface: list[UsageSurface]
    by_model: list[UsageModel]


class HealthResponse(BaseModel):
    status: str
    source_types: list[str] = Field(default_factory=list)
    # Whether chat accepts a per-message `filters.thinking` level (LiteLLM only);
    # the composer hides its thinking picker when false.
    chat_thinking: bool = False


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
