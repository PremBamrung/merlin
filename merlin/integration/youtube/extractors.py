from datetime import datetime
from io import BytesIO
from typing import Dict, List, Optional

import pytube
import requests
from PIL import Image
from pytube import Channel
from pytube.innertube import InnerTube
from youtube_transcript_api import YouTubeTranscriptApi

from merlin.utils import logger


class CustomPyYouTube(pytube.YouTube):
    """Extended YouTube class with custom client configuration."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = "WEB"
        self._vid_info = None

    @property
    def vid_info(self):
        """Parse the raw vid info and return the parsed result."""
        if self._vid_info:
            return self._vid_info

        self.innertube = InnerTube(
            use_oauth=self.use_oauth,
            allow_cache=self.allow_oauth_cache,
            client=self.client,
        )
        self._vid_info = self.innertube.player(self.video_id)
        return self._vid_info


class VideoExtractor:
    """Handles extraction of video metadata and information."""

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        import re

        regex = r"(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
        match = re.findall(regex, url)
        video_id = match[0] if match else None
        if video_id:
            logger.info(f"Successfully extracted video ID: {video_id}")
        else:
            logger.warning(f"Failed to extract video ID from URL: {url}")
        return video_id

    @staticmethod
    def extract_video_info(video_url: str) -> Optional[Dict[str, str]]:
        """Extract video metadata."""
        start_time = datetime.now()
        logger.info(f"Extracting video info for URL: {video_url}")

        try:
            yt = CustomPyYouTube(video_url)

            # Format duration
            duration = yt.length
            hours, remainder = divmod(duration, 3600)
            minutes, seconds = divmod(remainder, 60)
            formatted_duration = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

            # Get channel info
            channel_info = ChannelExtractor.extract_channel_info(yt.channel_url)

            result = {
                "title": yt.title,
                "channel": yt.author,
                "date": yt.publish_date.strftime("%d/%m/%Y"),
                "views": f"{yt.views:,}",
                "duration": formatted_duration,
                "subscribers": channel_info.get("subscribers", "N/A"),
                "videos": channel_info.get("videos", "N/A"),
            }

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Successfully extracted video info in {duration:.2f}s")
            return result

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(
                f"Failed to extract video info after {duration:.2f}s: {str(e)}"
            )
            return None

    @staticmethod
    def extract_thumbnail(video_id: str) -> Optional[Image.Image]:
        """Extract video thumbnail."""
        start_time = datetime.now()
        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        logger.info(f"Fetching thumbnail for video ID: {video_id}")

        try:
            response = requests.get(thumbnail_url)
            image = Image.open(BytesIO(response.content))
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Successfully fetched thumbnail in {duration:.2f}s")
            return image
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Failed to fetch thumbnail after {duration:.2f}s: {str(e)}")
            return None


class SubtitleExtractor:
    """Handles extraction and processing of video subtitles."""

    @staticmethod
    def extract_subtitles(video_id: str, languages: List[str]) -> Optional[List[Dict]]:
        """Extract subtitles in specified languages."""
        start_time = datetime.now()
        logger.info(f"Extracting subtitles for video ID: {video_id}")
        logger.debug(f"Attempting languages: {languages}")

        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            try:
                transcript = transcript_list.find_manually_created_transcript(languages)
                logger.info("Found manually created transcript")
            except:
                transcript = transcript_list.find_generated_transcript(languages)
                logger.info("Found auto-generated transcript")

            result = transcript.fetch()
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Successfully extracted subtitles in {duration:.2f}s")
            return result
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Failed to extract subtitles after {duration:.2f}s: {str(e)}")
            return None

    @staticmethod
    def extract_text(subtitles: List[Dict]) -> str:
        """Convert subtitles to plain text."""
        text = " ".join([sub["text"] for sub in subtitles])
        words_count = len(text.split())
        logger.info(f"Extracted text with {words_count:,} words")
        return text


class ChannelExtractor:
    """Handles extraction of YouTube channel information."""

    @staticmethod
    def extract_channel_info(channel_url: str) -> Dict[str, str]:
        """Extract channel metadata."""
        start_time = datetime.now()
        logger.info(f"Extracting channel info for URL: {channel_url}")

        try:
            channel = Channel(channel_url)
            result = {
                "videos": f"{len(channel.videos):,}",
                "total_views": f"{channel.views:,}",
            }
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Successfully extracted channel info in {duration:.2f}s")
            return result
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(
                f"Failed to extract channel info after {duration:.2f}s: {str(e)}"
            )
            return {}
