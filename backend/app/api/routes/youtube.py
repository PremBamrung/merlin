from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.models.database import get_db
from backend.app.models.schemas import (
    Video,
    VideoSummaryRequest,
    VideoSummaryResponse,
    VideoUpdate,
)
from backend.app.services.video_service import VideoService

router = APIRouter()


@router.post("/videos/process", response_model=VideoSummaryResponse)
async def process_video(
    request: VideoSummaryRequest, db: Session = Depends(get_db)
) -> VideoSummaryResponse:
    """Process a YouTube video and store its summary."""
    service = VideoService(db)
    video = await service.process_video(
        url=request.url,
        language=request.language,
        summary_length=request.summary_length,
        tags=request.tags,
    )
    return VideoSummaryResponse(video=video)


@router.get("/videos", response_model=List[Video])
async def get_videos(
    query: Optional[str] = None,
    tags: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
) -> List[Video]:
    """Get all videos with optional search and tag filtering."""
    service = VideoService(db)
    return await service.search_videos(query=query, tags=tags)


@router.get("/videos/{video_id}", response_model=Video)
async def get_video(video_id: str, db: Session = Depends(get_db)) -> Video:
    """Get a specific video by its YouTube ID."""
    service = VideoService(db)
    video = await service.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.put("/videos/{video_id}", response_model=Video)
async def update_video(
    video_id: str, video_update: VideoUpdate, db: Session = Depends(get_db)
) -> Video:
    """Update a video's information."""
    service = VideoService(db)
    video = await service.update_video(video_id, video_update)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.delete("/videos/{video_id}")
async def delete_video(video_id: str, db: Session = Depends(get_db)) -> dict:
    """Delete a video."""
    service = VideoService(db)
    if not await service.delete_video(video_id):
        raise HTTPException(status_code=404, detail="Video not found")
    return {"message": "Video deleted successfully"}
