from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from ..llm.service import LLMService
from .extractor import VideoExtractor


@dataclass
class VideoResult:
    video_id: str
    title: str
    channel: str
    date: datetime
    views: int
    duration: str
    words_count: Optional[int]
    subscribers: str
    videos_count: str
    transcript: str
    summary: str
    topics: Optional[Dict]
    timestamps: Optional[Dict]


class YouTubeService:
    def __init__(self):
        self.extractor = VideoExtractor()
        self.llm_service = LLMService()

    async def process_video(
        self, url: str, language: str = "english", summary_length: str = "short"
    ) -> VideoResult:
        """Process a YouTube video and return its data and summary."""
        # Extract video ID and metadata
        video_id = self.extractor.extract_video_id(url)
        if not video_id:
            raise ValueError("Invalid YouTube URL")

        # Get video metadata
        metadata = await self.extractor.get_video_metadata(video_id)

        # Get video transcript
        transcript = await self.extractor.get_transcript(video_id, language)
        if not transcript:
            raise ValueError("Could not fetch video transcript")

        # Process transcript with LLM
        summary_result = await self.llm_service.process_text(
            text=transcript,
            task="summarize",
            options={
                "language": language,
                "length": summary_length,
                "extract_topics": True,
                "extract_timestamps": True,
            },
        )

        # Return processed result
        return VideoResult(
            video_id=video_id,
            title=metadata["title"],
            channel=metadata["channel"],
            date=metadata["date"],
            views=metadata["views"],
            duration=metadata["duration"],
            words_count=len(transcript.split()),
            subscribers=metadata["subscribers"],
            videos_count=metadata["videos_count"],
            transcript=transcript,
            summary=summary_result["summary"],
            topics=summary_result.get("topics"),
            timestamps=summary_result.get("timestamps"),
        )

    async def get_video_metadata(self, video_id: str) -> dict:
        """Get video metadata without processing transcript."""
        return await self.extractor.get_video_metadata(video_id)

    async def get_transcript(
        self, video_id: str, language: str = "english"
    ) -> Optional[str]:
        """Get video transcript in specified language."""
        return await self.extractor.get_transcript(video_id, language)
