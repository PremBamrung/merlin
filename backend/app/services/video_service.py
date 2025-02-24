from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.models.database import Video
from backend.app.models.schemas import VideoCreate, VideoUpdate
from merlin.merlin.youtube import YouTubeService


class VideoService:
    def __init__(self, db: Session):
        self.db = db
        self.youtube_service = YouTubeService()

    async def process_video(
        self,
        url: str,
        language: str = "english",
        summary_length: str = "short",
        tags: Optional[str] = None,
    ) -> Video:
        """Process a YouTube video URL and store the results."""
        try:
            # Use Merlin library to process the video
            result = await self.youtube_service.process_video(
                url=url, language=language, summary_length=summary_length
            )

            # Create video data for database
            video_data = VideoCreate(
                video_id=result.video_id,
                title=result.title,
                channel=result.channel,
                date=result.date,
                views=result.views,
                duration=result.duration,
                words_count=result.words_count,
                subscribers=result.subscribers,
                videos_count=result.videos_count,
                transcript=result.transcript,
                summary=result.summary,
                topics=result.topics,
                timestamps=result.timestamps,
                tags=tags,
                summary_length=summary_length,
            )

            return await self.create_video(video_data)

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error processing video: {str(e)}"
            )

    async def create_video(self, video_data: VideoCreate) -> Video:
        """Create a new video entry in the database."""
        db_video = Video(**video_data.model_dump())
        self.db.add(db_video)
        self.db.commit()
        self.db.refresh(db_video)
        return db_video

    async def get_video(self, video_id: str) -> Optional[Video]:
        """Get a video by its YouTube ID."""
        return self.db.query(Video).filter(Video.video_id == video_id).first()

    async def get_all_videos(self) -> list[Video]:
        """Get all videos from the database."""
        return self.db.query(Video).order_by(Video.created_at.desc()).all()

    async def update_video(
        self, video_id: str, video_update: VideoUpdate
    ) -> Optional[Video]:
        """Update a video's information."""
        db_video = await self.get_video(video_id)
        if not db_video:
            return None

        update_data = video_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_video, field, value)

        db_video.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_video)
        return db_video

    async def delete_video(self, video_id: str) -> bool:
        """Delete a video from the database."""
        db_video = await self.get_video(video_id)
        if not db_video:
            return False

        self.db.delete(db_video)
        self.db.commit()
        return True

    async def search_videos(
        self, query: Optional[str] = None, tags: Optional[list[str]] = None
    ) -> list[Video]:
        """Search videos by title, channel, content, or tags."""
        videos_query = self.db.query(Video)

        if query:
            search_filter = (
                (Video.title.ilike(f"%{query}%"))
                | (Video.channel.ilike(f"%{query}%"))
                | (Video.summary.ilike(f"%{query}%"))
            )
            videos_query = videos_query.filter(search_filter)

        if tags:
            for tag in tags:
                videos_query = videos_query.filter(Video.tags.ilike(f"%{tag}%"))

        return videos_query.order_by(Video.created_at.desc()).all()
