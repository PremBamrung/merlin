# models.py
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///merlin.db"

Base = declarative_base()


class YouTubeVideoSummary(Base):
    __tablename__ = "youtube_video_summary"
    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String(255), unique=False, nullable=False)
    title = Column(String(255))
    channel = Column(String(255))
    date = Column(DateTime)
    views = Column(Integer)
    duration = Column(String(255))
    words_count = Column(Integer)
    subscribers = Column(String(255))
    videos = Column(String(255))
    summary = Column(Text)
    subtitles = Column(Text)  # New column for storing subtitles
    date_added = Column(
        DateTime, default=datetime.utcnow
    )  # New column for storing the added date


engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)
