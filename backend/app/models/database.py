from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import settings

Base = declarative_base()


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String, unique=True, index=True)
    title = Column(String)
    channel = Column(String)
    date = Column(DateTime)
    views = Column(Integer)
    duration = Column(String)
    words_count = Column(Integer)
    subscribers = Column(String)
    videos_count = Column(String)
    transcript = Column(Text)
    summary = Column(Text)
    tags = Column(String)  # Comma-separated tags
    summary_length = Column(String)  # short, medium, or long
    topics = Column(JSON)  # Extracted topics and key points
    timestamps = Column(JSON)  # Important moments in the video
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


engine = create_engine(settings.SQLALCHEMY_DATABASE_URI, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
