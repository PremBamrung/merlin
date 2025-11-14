# models.py
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from merlin.utils import logger

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
    tags = Column(String(500))  # Comma-separated tags
    summary_length = Column(String(20))  # short, medium, or long
    llm_model = Column(String(100))  # LLM model used for summarization
    topics = Column(JSON)  # Extracted topics and key points
    timestamps = Column(JSON)  # Important moments in the video
    error_message = Column(Text)  # Store any processing errors


engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database and run migrations."""
    Base.metadata.create_all(bind=engine)
    migrate_db()


def migrate_db():
    """Run database migrations to add new columns."""
    from sqlalchemy import inspect, text

    try:
        inspector = inspect(engine)
        # Check if table exists
        if "youtube_video_summary" not in inspector.get_table_names():
            logger.info(
                "Table youtube_video_summary does not exist yet, will be created by create_all"
            )
            return

        columns = [
            col["name"] for col in inspector.get_columns("youtube_video_summary")
        ]

        # Add llm_model column if it doesn't exist
        if "llm_model" not in columns:
            with engine.connect() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE youtube_video_summary ADD COLUMN llm_model VARCHAR(100)"
                    )
                )
                conn.commit()
                logger.info("Added llm_model column to youtube_video_summary table")
    except Exception as e:
        logger.warning(
            f"Migration check failed (this is OK for new databases): {str(e)}"
        )
