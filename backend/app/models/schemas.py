from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class VideoBase(BaseModel):
    video_id: str
    title: str
    channel: str
    date: datetime
    views: int
    duration: str
    words_count: Optional[int] = None
    subscribers: Optional[str] = None
    videos_count: Optional[str] = None
    tags: Optional[str] = None
    summary_length: Optional[str] = Field(None, description="short, medium, or long")


class VideoCreate(VideoBase):
    transcript: str
    summary: str
    topics: Optional[Dict] = None
    timestamps: Optional[Dict] = None


class VideoUpdate(BaseModel):
    summary: Optional[str] = None
    tags: Optional[str] = None
    summary_length: Optional[str] = None
    topics: Optional[Dict] = None
    timestamps: Optional[Dict] = None


class Video(VideoBase):
    id: int
    transcript: str
    summary: str
    topics: Optional[Dict] = None
    timestamps: Optional[Dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VideoSummaryRequest(BaseModel):
    url: str
    language: str = "english"
    summary_length: str = Field("short", description="short, medium, or long")
    tags: Optional[str] = None


class VideoSummaryResponse(BaseModel):
    video: Video
    message: str = "Video processed successfully"
