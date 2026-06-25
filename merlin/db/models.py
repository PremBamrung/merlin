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

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String, Text
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
    topics = Column(Text)  # JSON object: {"Topic": "timestamp"}

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
