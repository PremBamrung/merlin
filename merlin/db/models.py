"""
New unified SQLAlchemy models for the Merlin knowledge base.

Design:
- knowledge_items: source-agnostic core table (one row per ingested item)
- youtube_metadata: YouTube-specific fields (one-to-one with knowledge_items)
- background_tasks: async job tracking
- embeddings: vector chunks for RAG (Phase 3)

The old youtube_video_summary table is NEVER touched here.
"""

from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _now():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id = Column(String(36), primary_key=True, default=_uuid)
    source_type = Column(
        String(50), nullable=False
    )  # youtube | article | pdf | podcast
    source_id = Column(String(512), nullable=False)  # video_id, URL hash, etc.

    title = Column(String(512))
    author = Column(String(255))  # channel name, article author, etc.
    published_at = Column(DateTime)
    ingested_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    # Content
    raw_content = Column(Text)  # full transcript / article text
    summary = Column(Text)
    summary_length = Column(String(20))  # short | long  (legacy rows may be "medium")

    # Organisation
    tags = Column(Text)  # JSON array string: ["ai","python"]
    # Per-item section map scraped from the summary ({"heading": "12:34"}), used
    # to jump *within* one summary. NOT the cross-corpus taxonomy — that's the
    # `topics`/`item_topics` tables. (Renamed from `topics`; migration 009.)
    sections = Column(Text)  # JSON object: {"Section heading": "timestamp"}

    # Processing metadata
    llm_model = Column(String(100))
    word_count = Column(Integer)
    status = Column(
        String(20), default="pending"
    )  # pending|processing|completed|failed
    error_message = Column(Text)

    # Consumption state (Feed) — nullable timestamps, not booleans, so we keep
    # *when* it happened for free. read_at IS NULL ⇔ unread; saved_at the ★ flag.
    read_at = Column(DateTime)
    saved_at = Column(DateTime)

    # Relationships
    youtube_metadata = relationship(
        "YouTubeMetadata",
        back_populates="knowledge_item",
        uselist=False,
        cascade="all, delete-orphan",
    )
    background_tasks = relationship("BackgroundTask", back_populates="knowledge_item")
    embeddings = relationship(
        "Embedding", back_populates="knowledge_item", cascade="all, delete-orphan"
    )
    item_topics = relationship(
        "ItemTopic", back_populates="knowledge_item", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_knowledge_source", "source_type", "source_id", unique=True),
        Index("ix_knowledge_status", "status"),
        Index("ix_knowledge_ingested", "ingested_at"),
        Index("ix_knowledge_read", "read_at"),
        Index("ix_knowledge_saved", "saved_at"),
    )


class YouTubeMetadata(Base):
    __tablename__ = "youtube_metadata"

    knowledge_item_id = Column(
        String(36),
        ForeignKey("knowledge_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    video_id = Column(String(20), nullable=False, unique=True)
    channel = Column(String(255))
    views = Column(Integer)
    duration = Column(String(20))  # HH:MM:SS
    subscribers = Column(String(50))
    videos_count = Column(String(50))
    timestamps = Column(Text)  # JSON: {"topic": "00:01:23"}
    detected_language = Column(String(20))
    thumbnail_url = Column(String(512))
    description = Column(Text)  # video description (grounds summary + chat)

    knowledge_item = relationship("KnowledgeItem", back_populates="youtube_metadata")


class BackgroundTask(Base):
    __tablename__ = "background_tasks"

    id = Column(String(36), primary_key=True, default=_uuid)
    task_type = Column(String(100), nullable=False)  # ingest_youtube | ingest_article
    status = Column(
        String(20), nullable=False, default="queued"
    )  # queued|processing|completed|failed
    progress = Column(Integer, default=0)  # 0-100
    message = Column(Text)
    title = Column(Text)  # document title, set once known (e.g. after metadata fetch)

    input_data = Column(Text)  # JSON of original request
    result_data = Column(Text)  # JSON of result (knowledge_item_id, etc.)
    error = Column(Text)

    created_at = Column(DateTime, default=_now)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    knowledge_item_id = Column(
        String(36), ForeignKey("knowledge_items.id"), nullable=True
    )
    knowledge_item = relationship("KnowledgeItem", back_populates="background_tasks")

    __table_args__ = (
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_created", "created_at"),
    )


class Embedding(Base):
    """Vector chunks for semantic search (Phase 3)."""

    __tablename__ = "embeddings"

    id = Column(String(36), primary_key=True, default=_uuid)
    knowledge_item_id = Column(
        String(36), ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Text)  # JSON-serialised float32 list (Phase 3)
    embedding_model = Column(String(100))

    knowledge_item = relationship("KnowledgeItem", back_populates="embeddings")

    __table_args__ = (
        Index("ix_embeddings_item", "knowledge_item_id", "chunk_index", unique=True),
    )


class Topic(Base):
    """A cross-corpus navigation category — the Feed's primary filter.

    Closed, user-curated taxonomy (small: ~10–30 rows). The LLM classifier
    only ever *picks from* active topics; new topics are born via the batch
    proposal pipeline (services.topics.propose_topics) and a human accept step.
    `slug` is the stable url/filter key; `status` is active|archived (a pending
    proposal lives in topic_proposals, not here). `origin` records provenance:
    seed (seeded script) | user (created by hand) | proposed (from a pipeline).
    """

    __tablename__ = "topics"

    id = Column(String(36), primary_key=True, default=_uuid)
    label = Column(String(120), nullable=False)  # display name, e.g. "Coding"
    slug = Column(String(120), nullable=False, unique=True)  # filter key, "coding"
    status = Column(String(20), nullable=False, default="active")  # active|archived
    origin = Column(String(20), nullable=False, default="user")  # seed|user|proposed
    description = Column(Text)  # optional disambiguator, also fed to the classifier
    created_at = Column(DateTime, default=_now)

    item_topics = relationship(
        "ItemTopic", back_populates="topic", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_topics_status", "status"),)


class ItemTopic(Base):
    """Assignment of a topic to a knowledge item (many-to-many).

    Each item gets one primary topic + up to 2 secondary. `is_primary` is the
    Feed's default grouping; a partial unique index (see migration 010) enforces
    at most one primary per item. `assigned_by` is llm|user — user rows are never
    clobbered by re-classification (see services.classify).
    """

    __tablename__ = "item_topics"

    knowledge_item_id = Column(
        String(36),
        ForeignKey("knowledge_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    topic_id = Column(
        String(36),
        ForeignKey("topics.id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_primary = Column(Boolean, nullable=False, default=False)
    assigned_by = Column(String(20), nullable=False, default="llm")  # llm|user
    confidence = Column(Float)  # optional, LLM self-report
    created_at = Column(DateTime, default=_now)

    knowledge_item = relationship("KnowledgeItem", back_populates="item_topics")
    topic = relationship("Topic", back_populates="item_topics")

    __table_args__ = (
        Index("ix_item_topics_topic", "topic_id"),
        # At most one primary topic per item. Partial unique index — SQLite
        # supports the WHERE clause (also created by hand in migration 010).
        Index(
            "ux_item_topics_primary",
            "knowledge_item_id",
            unique=True,
            sqlite_where=text("is_primary"),
        ),
    )


class TopicProposal(Base):
    """A candidate topic emitted by the batch proposal pipeline (§7), awaiting a
    human accept/merge/reject.

    `item_ids` is a JSON snapshot of the member item ids at propose time (may go
    stale — accept tolerates drift). `batch_id` groups one pipeline run's
    proposals; a new run supersedes still-pending rows from prior batches.
    `status` is pending|accepted|rejected|superseded.
    """

    __tablename__ = "topic_proposals"

    id = Column(String(36), primary_key=True, default=_uuid)
    proposed_label = Column(String(120), nullable=False)
    item_ids = Column(Text, nullable=False)  # JSON array of member item ids
    rationale = Column(Text)  # one line: what these items share
    status = Column(String(20), nullable=False, default="pending")
    batch_id = Column(String(36))
    created_at = Column(DateTime, default=_now)

    __table_args__ = (Index("ix_topic_proposals_status", "status"),)


class ShareToken(Base):
    __tablename__ = "share_tokens"

    id = Column(String(36), primary_key=True, default=_uuid)
    token = Column(String(8), unique=True, nullable=False, index=True)
    knowledge_item_id = Column(
        String(36), ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime, default=_now)


class DigestAction(Base):
    __tablename__ = "digest_actions"

    id = Column(String(36), primary_key=True, default=_uuid)
    knowledge_item_id = Column(
        String(36), ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False
    )
    action = Column(String(20), nullable=False)  # "ingest" | "skip"
    created_at = Column(DateTime, default=_now)


class LlmUsage(Base):
    """One LLM / transcription call's usage — for cost visibility only.

    Written after each spend site (chat `on_complete`, ingest `persist_result`).
    Nothing reads this to gate or throttle; it backs the Insights spend charts
    and per-item cost. `cost_usd` is the provider-reported cost when available,
    else computed from `merlin.llm_pricing`, else NULL (unknown model — Insights
    treats NULL as "unknown", not "$0"). `meta` stashes cache tokens / tool_calls
    / thread id as JSON.
    """

    __tablename__ = "llm_usage"

    id = Column(String(36), primary_key=True, default=_uuid)
    created_at = Column(DateTime, default=_now)
    surface = Column(String(20), nullable=False)  # chat|summarize|transcribe
    provider = Column(String(20))  # openrouter|azure|groq
    model = Column(String(100))
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    audio_seconds = Column(Float)
    requests = Column(Integer)  # model round-trips (chat tool loop)
    cost_usd = Column(Float)
    knowledge_item_id = Column(
        String(36), ForeignKey("knowledge_items.id", ondelete="SET NULL"), nullable=True
    )
    meta = Column(Text)  # JSON

    __table_args__ = (
        Index("ix_llm_usage_created", "created_at"),
        Index("ix_llm_usage_surface", "surface"),
        Index("ix_llm_usage_item", "knowledge_item_id"),
    )


class ChatThread(Base):
    """A saved, continuable library-wide chat conversation.

    `title` is NULL until the cheap title call returns (the UI falls back to a
    message preview). `updated_at` is bumped on every saved turn; the sidebar
    sorts by it. Messages cascade-delete with the thread.
    """

    __tablename__ = "chat_threads"

    id = Column(String(36), primary_key=True, default=_uuid)
    title = Column(String(512))
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)
    # Denormalized sidebar fields, refreshed on every save_thread, so the
    # thread-list endpoint reads one row per thread instead of loading every
    # message's (potentially large) parts blob just to count + preview them.
    message_count = Column(Integer, default=0)
    preview = Column(String(512))  # first user message text, for titleless rows

    messages = relationship(
        "ChatMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="ChatMessage.seq",
    )

    __table_args__ = (Index("ix_chat_threads_updated", "updated_at"),)


class ChatMessage(Base):
    """One turn within a `ChatThread`.

    `parts` stores the Vercel AI SDK `UIMessage` parts verbatim as a JSON array
    (text, reasoning, tool calls/results, citation data-parts) so a reopened
    thread renders identically and replays cleanly as agent history.
    """

    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=_uuid)
    thread_id = Column(
        String(36),
        ForeignKey("chat_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    seq = Column(Integer, nullable=False)
    role = Column(String(20), nullable=False)  # user | assistant
    parts = Column(Text)  # JSON array of UIMessage parts
    created_at = Column(DateTime, default=_now)

    thread = relationship("ChatThread", back_populates="messages")

    __table_args__ = (Index("ix_chat_messages_thread_seq", "thread_id", "seq"),)
