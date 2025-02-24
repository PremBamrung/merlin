import re
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import parse_qs, urlparse

import httpx
from youtube_transcript_api import YouTubeTranscriptApi


class VideoExtractor:
    def __init__(self):
        self.youtube_api_key = None  # Will be loaded from environment
        self.base_url = "https://www.googleapis.com/youtube/v3"
        self.client = httpx.AsyncClient()

    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from various YouTube URL formats."""
        patterns = [r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", r"^([0-9A-Za-z_-]{11})$"]

        # Parse URL and try to get video ID from query parameters
        parsed_url = urlparse(url)
        if parsed_url.query:
            query_params = parse_qs(parsed_url.query)
            if "v" in query_params:
                return query_params["v"][0]

        # Try matching patterns
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    async def get_video_metadata(self, video_id: str) -> Dict:
        """Get video metadata from YouTube API."""
        # For now, using a simpler approach without API key
        # In production, this should use the YouTube Data API
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            response = await self.client.get(url)
            html = response.text

            # Basic metadata extraction (this should be replaced with proper API calls)
            title = self._extract_meta_content(html, "title")
            channel = self._extract_meta_content(html, "channelName")

            # Placeholder data (should be replaced with actual API data)
            return {
                "title": title or "Unknown Title",
                "channel": channel or "Unknown Channel",
                "date": datetime.now(),  # Should be actual upload date
                "views": 0,  # Should be actual view count
                "duration": "0:00",  # Should be actual duration
                "subscribers": "N/A",  # Should be actual subscriber count
                "videos_count": "N/A",  # Should be actual video count
            }
        except Exception as e:
            raise ValueError(f"Failed to fetch video metadata: {str(e)}")

    async def get_transcript(
        self, video_id: str, language: str = "english"
    ) -> Optional[str]:
        """Get video transcript in specified language."""
        try:
            # Get available transcripts
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Try to get transcript in specified language
            try:
                transcript = transcript_list.find_transcript([language])
            except:
                # If specified language not found, try English or auto-generated
                try:
                    transcript = transcript_list.find_transcript(["en"])
                except:
                    # Get auto-generated transcript as last resort
                    transcript = transcript_list.find_manually_created_transcript()

            # Fetch the transcript
            transcript_parts = transcript.fetch()

            # Combine transcript parts into single text
            return " ".join(part["text"] for part in transcript_parts)

        except Exception as e:
            print(f"Error fetching transcript: {str(e)}")
            return None

    def _extract_meta_content(self, html: str, property_name: str) -> Optional[str]:
        """Extract content from meta tags in HTML."""
        pattern = f'meta property="og:{property_name}" content="([^"]+)"'
        match = re.search(pattern, html)
        return match.group(1) if match else None
