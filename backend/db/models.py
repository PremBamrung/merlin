"""
New unified SQLAlchemy models for the Merlin knowledge base.

Design:
- knowledge_items: source-agnostic core table (one row per ingested item)
- youtube_metadata: YouTube-specific fields (one-to-one with knowledge_items)
- background_tasks: async job tracking
- embeddings: vector chunks for RAG (Phase 3)

The old youtube_video_summary table is NEVER touched here.
"""

import uuid
from datetime import datetime, timezone

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
    source_type = Column(String(50), nullable=False)  # youtube | article | pdf | podcast
    source_id = Column(String(512), nullable=False)   # video_id, URL hash, etc.

    title = Column(String(512))
    author = Column(String(255))          # channel name, article author, etc.
    published_at = Column(DateTime)
    ingested_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    # Content
    raw_content = Column(Text)            # full transcript / article text
    summary = Column(Text)
    summary_length = Column(String(20))   # short | medium | long

    # Organisation
    tags = Column(Text)                   # JSON array string: ["ai","python"]
    topics = Column(Text)                 # JSON object: {"Topic": "timestamp"}

    # Processing metadata
    llm_model = Column(String(100))
    word_count = Column(Integer)
    status = Column(String(20), default="pending")  # pending|processing|completed|failed
    error_message = Column(Text)

    # Relationships
    youtube_metadata = relationship(
        "YouTubeMetadata", back_populates="knowledge_item", uselist=False, cascade="all, delete-orphan"
    )
    background_tasks = relationship("BackgroundTask", back_populates="knowledge_item")
    embeddings = relationship("Embedding", back_populates="knowledge_item", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_knowledge_source", "source_type", "source_id", unique=True),
        Index("ix_knowledge_status", "status"),
        Index("ix_knowledge_ingested", "ingested_at"),
    )


class YouTubeMetadata(Base):
    __tablename__ = "youtube_metadata"

    knowledge_item_id = Column(
        String(36), ForeignKey("knowledge_items.id", ondelete="CASCADE"), primary_key=True
    )
    video_id = Column(String(20), nullable=False, unique=True)
    channel = Column(String(255))
    views = Column(Integer)
    duration = Column(String(20))         # HH:MM:SS
    subscribers = Column(String(50))
    videos_count = Column(String(50))
    timestamps = Column(Text)             # JSON: {"topic": "00:01:23"}
    detected_language = Column(String(20))
    thumbnail_url = Column(String(512))

    knowledge_item = relationship("KnowledgeItem", back_populates="youtube_metadata")


class BackgroundTask(Base):
    __tablename__ = "background_tasks"

    id = Column(String(36), primary_key=True, default=_uuid)
    task_type = Column(String(100), nullable=False)   # ingest_youtube | ingest_article
    status = Column(String(20), nullable=False, default="queued")  # queued|processing|completed|failed
    progress = Column(Integer, default=0)             # 0-100
    message = Column(Text)

    input_data = Column(Text)             # JSON of original request
    result_data = Column(Text)            # JSON of result (knowledge_item_id, etc.)
    error = Column(Text)

    created_at = Column(DateTime, default=_now)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    knowledge_item_id = Column(String(36), ForeignKey("knowledge_items.id"), nullable=True)
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
    embedding = Column(Text)              # JSON-serialised float32 list (Phase 3)
    embedding_model = Column(String(100))

    knowledge_item = relationship("KnowledgeItem", back_populates="embeddings")

    __table_args__ = (
        Index("ix_embeddings_item", "knowledge_item_id", "chunk_index", unique=True),
    )
