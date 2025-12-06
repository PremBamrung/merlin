from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from merlin.database.models import YouTubeVideoSummary
from merlin.utils import logger


class VideoRepository:
    """Repository for video-related database operations."""

    @staticmethod
    def save_video_summary(
        session: Session,
        video_info: Dict,
        text: str,
        summary_text: str,
        subtitles_text: str,
        tags: str = None,
        summary_length: str = None,
        llm_model: str = None,
        topics: Dict = None,
        timestamps: Dict = None,
        error_message: str = None,
    ) -> YouTubeVideoSummary:
        """Save video summary to database with additional metadata."""
        try:
            views = int(video_info["views"].replace(",", "").replace(" views", ""))
            date = datetime.strptime(video_info["date"], "%d/%m/%Y")

            video_summary = YouTubeVideoSummary(
                video_id=video_info["video_id"],
                title=video_info["title"],
                channel=video_info["channel"],
                date=date,
                views=views,
                duration=video_info["duration"],
                words_count=len(text.split()),
                subscribers=video_info["subscribers"],
                videos=video_info["videos"],
                summary=summary_text,
                subtitles=subtitles_text,
                date_added=datetime.utcnow(),
                tags=tags,
                summary_length=summary_length,
                llm_model=llm_model,
                topics=topics,
                timestamps=timestamps,
                error_message=error_message,
            )
            session.add(video_summary)
            logger.info(f"Saved summary for video ID: {video_info['video_id']}")
            return video_summary
        except Exception as e:
            logger.error(f"Error saving video summary: {str(e)}")
            raise

    @staticmethod
    def get_video_by_id(session: Session, video_id: str) -> Optional[Dict]:
        """Retrieve video summary by video ID."""
        try:
            video = (
                session.query(YouTubeVideoSummary).filter_by(video_id=video_id).first()
            )
            if video:
                logger.info(f"Retrieved video summary for ID: {video_id}")
                return {
                    "title": video.title,
                    "channel": video.channel,
                    "date": video.date.strftime("%d/%m/%Y"),
                    "views": f"{video.views:,}",
                    "duration": video.duration,
                    "subscribers": video.subscribers,
                    "videos": video.videos,
                    "summary": video.summary,
                    "subtitles": video.subtitles,
                    "words_count": video.words_count,
                    "video_id": video.video_id,
                    "cached": True,
                }
            logger.info(f"No video found for ID: {video_id}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving video: {str(e)}")
            raise

    @staticmethod
    def get_all_videos(session: Session) -> List[Dict]:
        """Retrieve all video summaries."""
        try:
            videos = session.query(YouTubeVideoSummary).all()
            logger.info(f"Retrieved {len(videos)} video summaries")
            # Convert ORM objects to dictionaries while session is still open
            return [
                {
                    "id": video.id,
                    "video_id": video.video_id,
                    "title": video.title,
                    "channel": video.channel,
                    "date": video.date,
                    "views": video.views,
                    "duration": video.duration,
                    "words_count": video.words_count,
                    "subscribers": video.subscribers,
                    "videos": video.videos,
                    "summary": video.summary,
                    "subtitles": video.subtitles,
                    "date_added": video.date_added,
                    "tags": video.tags,
                    "summary_length": video.summary_length,
                    "llm_model": video.llm_model,
                    "topics": video.topics,
                    "timestamps": video.timestamps,
                    "error_message": video.error_message,
                }
                for video in videos
            ]
        except Exception as e:
            logger.error(f"Error retrieving videos: {str(e)}")
            raise

    @staticmethod
    def save_or_update_video_info_and_subtitles(
        session: Session,
        video_info: Dict,
        subtitles_text: str,
    ) -> YouTubeVideoSummary:
        """Save or update video info and subtitles, even if summary doesn't exist yet.

        This allows caching video info and subtitles separately from the summary,
        so they can be reused if summary generation fails or needs to be redone.
        """
        try:
            views = int(video_info["views"].replace(",", "").replace(" views", ""))
            date = datetime.strptime(video_info["date"], "%d/%m/%Y")

            # Check if video already exists
            existing_video = (
                session.query(YouTubeVideoSummary)
                .filter_by(video_id=video_info["video_id"])
                .first()
            )

            if existing_video:
                # Update existing record with video info and subtitles
                # Preserve summary and other fields if they exist
                existing_video.title = video_info["title"]
                existing_video.channel = video_info["channel"]
                existing_video.date = date
                existing_video.views = views
                existing_video.duration = video_info["duration"]
                existing_video.subscribers = video_info["subscribers"]
                existing_video.videos = video_info["videos"]
                existing_video.subtitles = subtitles_text
                existing_video.words_count = len(subtitles_text.split())
                # Don't update summary, topics, timestamps, etc. if they exist
                logger.info(
                    f"Updated video info and subtitles for ID: {video_info['video_id']}"
                )
                return existing_video
            else:
                # Create new record with video info and subtitles (no summary yet)
                video_summary = YouTubeVideoSummary(
                    video_id=video_info["video_id"],
                    title=video_info["title"],
                    channel=video_info["channel"],
                    date=date,
                    views=views,
                    duration=video_info["duration"],
                    words_count=len(subtitles_text.split()),
                    subscribers=video_info["subscribers"],
                    videos=video_info["videos"],
                    summary=None,  # No summary yet
                    subtitles=subtitles_text,
                    date_added=datetime.utcnow(),
                )
                session.add(video_summary)
                logger.info(
                    f"Saved video info and subtitles for ID: {video_info['video_id']}"
                )
                return video_summary
        except Exception as e:
            logger.error(f"Error saving video info and subtitles: {str(e)}")
            raise

    @staticmethod
    def update_video_summary_only(
        session: Session,
        video_id: str,
        summary_text: str,
        summary_length: str = None,
        llm_model: str = None,
        topics: Dict = None,
        timestamps: Dict = None,
        error_message: str = None,
    ) -> bool:
        """Update only the summary-related fields of an existing video record.

        This allows updating the summary without re-extracting video info and subtitles.
        """
        try:
            video = (
                session.query(YouTubeVideoSummary).filter_by(video_id=video_id).first()
            )
            if video:
                video.summary = summary_text
                if summary_length is not None:
                    video.summary_length = summary_length
                if llm_model is not None:
                    video.llm_model = llm_model
                if topics is not None:
                    video.topics = topics
                if timestamps is not None:
                    video.timestamps = timestamps
                if error_message is not None:
                    video.error_message = error_message
                logger.info(f"Updated summary for video ID: {video_id}")
                return True
            logger.warning(f"No video found to update summary for ID: {video_id}")
            return False
        except Exception as e:
            logger.error(f"Error updating video summary: {str(e)}")
            raise

    @staticmethod
    def clear_video_summary_only(session: Session, video_id: str) -> bool:
        """Clear only the summary-related fields, keeping video info and subtitles.

        This allows redoing the summary without re-extracting video info and subtitles.
        """
        try:
            video = (
                session.query(YouTubeVideoSummary).filter_by(video_id=video_id).first()
            )
            if video:
                video.summary = None
                video.summary_length = None
                video.llm_model = None
                video.topics = None
                video.timestamps = None
                video.error_message = None
                logger.info(
                    f"Cleared summary for video ID: {video_id} (kept video info and subtitles)"
                )
                return True
            logger.warning(f"No video found to clear summary for ID: {video_id}")
            return False
        except Exception as e:
            logger.error(f"Error clearing video summary: {str(e)}")
            raise

    @staticmethod
    def delete_video(session: Session, video_id: str) -> bool:
        """Delete a video summary by ID."""
        try:
            video = (
                session.query(YouTubeVideoSummary).filter_by(video_id=video_id).first()
            )
            if video:
                session.delete(video)
                logger.info(f"Deleted video summary for ID: {video_id}")
                return True
            logger.warning(f"No video found to delete for ID: {video_id}")
            return False
        except Exception as e:
            logger.error(f"Error deleting video: {str(e)}")
            raise
