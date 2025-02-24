from typing import Dict, List, Optional

from PIL import Image

from merlin.database.manager import DatabaseManager
from merlin.database.repositories import VideoRepository
from merlin.integration.youtube.extractors import (
    ChannelExtractor,
    SubtitleExtractor,
    VideoExtractor,
)
from merlin.integration.youtube.summarizer import VideoSummarizer
from merlin.utils import logger


class YouTubeService:
    """Main service class for YouTube video processing."""

    def __init__(self):
        """Initialize service with required components."""
        self.db = DatabaseManager()
        self.summarizer = VideoSummarizer()
        self.video_extractor = VideoExtractor()
        self.subtitle_extractor = SubtitleExtractor()

    def get_cached_video(self, video_id: str) -> Optional[Dict]:
        """Retrieve cached video summary."""
        return self.db.execute_with_session(
            lambda session: VideoRepository.get_video_by_id(session, video_id)
        )

    def delete_cached_video(self, video_id: str) -> bool:
        """Delete cached video summary."""
        return self.db.execute_with_session(
            lambda session: VideoRepository.delete_video(session, video_id)
        )

    def get_all_videos(self) -> List[Dict]:
        """Retrieve all cached video summaries."""
        return self.db.execute_with_session(VideoRepository.get_all_videos)

    def process_video(
        self,
        url: str,
        lang: str = "english",
        summary_length: str = "medium",
        streaming: bool = False,
    ) -> Optional[Dict]:
        """Process a YouTube video URL.

        Coordinates the entire video processing pipeline:
        1. Extract video ID and info
        2. Get subtitles
        3. Generate summary
        4. Save to database

        Args:
            url: YouTube video URL
            lang: Target language for summary
            streaming: Whether to stream the summary response

        Returns:
            Dictionary containing video information and summary,
            or None if processing fails
        """
        # Extract video ID
        video_id = self.video_extractor.extract_video_id(url)
        if not video_id:
            logger.error("Failed to extract video ID")
            return None

        # Extract video info
        video_info = self.video_extractor.extract_video_info(url)
        if not video_info:
            logger.error("Failed to extract video info")
            return None
        video_info["video_id"] = video_id

        # Extract subtitles
        subtitles = self.subtitle_extractor.extract_subtitles(
            video_id, ["en", "fr", "de"]
        )
        if not subtitles:
            logger.error("Failed to extract subtitles")
            return None

        # Convert subtitles to text
        text = self.subtitle_extractor.extract_text(subtitles)
        if not text:
            logger.error("Failed to extract text from subtitles")
            return None

        try:
            # Generate summary with new parameters
            if streaming:
                try:
                    # First yield the metadata as a dict
                    yield {"type": "metadata", "video_info": video_info, "text": text}

                    # Then stream the summary chunks
                    summary_text = ""
                    for chunk in self.summarizer.summarize(
                        subtitles=text,
                        title=video_info["title"],
                        channel=video_info["channel"],
                        lang=lang,
                        summary_length=summary_length,
                        streaming=True,
                    ):
                        summary_text += chunk
                        yield {"type": "chunk", "content": chunk}

                    # Extract topics and timestamps after streaming
                    try:
                        topics, timestamps = (
                            self.summarizer.extract_topics_and_timestamps(summary_text)
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to extract topics and timestamps: {str(e)}"
                        )
                        topics, timestamps = {}, {}

                    # Finally yield the summary metadata
                    yield {
                        "type": "summary_metadata",
                        "summary": summary_text,
                        "topics": topics,
                        "timestamps": timestamps,
                    }
                except Exception as e:
                    logger.error(f"Error in streaming mode: {str(e)}")
                    yield {"type": "error", "message": str(e)}
            else:
                summary, topics, timestamps = self.summarizer.summarize(
                    subtitles=text,
                    title=video_info["title"],
                    channel=video_info["channel"],
                    lang=lang,
                    summary_length=summary_length,
                    streaming=False,
                )

                # Save to database with new fields
                self.db.execute_with_session(
                    lambda session: VideoRepository.save_video_summary(
                        session,
                        video_info,
                        text,
                        summary,
                        text,
                        summary_length=summary_length,
                        topics=topics,
                        timestamps=timestamps,
                    )
                )

                return {
                    "video_info": video_info,
                    "summary": summary,
                    "text": text,
                    "topics": topics,
                    "timestamps": timestamps,
                }

        except Exception as e:
            logger.error(f"Error processing video: {str(e)}")
            return None

    def extract_thumbnail(self, video_id: str) -> Optional[Image.Image]:
        """Extract video thumbnail."""
        return self.video_extractor.extract_thumbnail(video_id)
