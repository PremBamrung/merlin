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
    ) -> YouTubeVideoSummary:
        """Save video summary to database."""
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
    def get_all_videos(session: Session) -> List[YouTubeVideoSummary]:
        """Retrieve all video summaries."""
        try:
            videos = session.query(YouTubeVideoSummary).all()
            logger.info(f"Retrieved {len(videos)} video summaries")
            return videos
        except Exception as e:
            logger.error(f"Error retrieving videos: {str(e)}")
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
