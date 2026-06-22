from datetime import datetime
from io import BytesIO
from typing import Dict, List, Optional

from PIL import Image
import pytube
from pytube import Channel
from pytube.innertube import InnerTube
import requests
from youtube_transcript_api import YouTubeTranscriptApi

from merlin.config import settings
from merlin.core.logging import logger
from merlin.core.rate_limit import MinIntervalRateLimiter

# Shared across all ingest workers so concurrent video ingestions don't
# burst-hit YouTube's transcript endpoint and get the IP banned (HTTP 429).
# Once a ban is detected it trips a process-wide cooldown (see trip_cooldown);
# while cooled down, subtitle fetching is skipped in favour of audio transcription
# so the IP can recover instead of being hammered further.
_subtitle_rate_limiter = MinIntervalRateLimiter(
    settings.youtube_subtitle_min_interval,
    name="youtube-subtitles",
    cooldown_seconds=settings.youtube_subtitle_cooldown,
    cooldown_max=settings.youtube_subtitle_cooldown_max,
)


def _is_ip_block(error_msg: str) -> bool:
    """Heuristically detect a YouTube rate-limit / IP-block error message."""
    m = error_msg.lower()
    return (
        "429" in m
        or "too many requests" in m
        or "blocking requests from your ip" in m
        or "requestblocked" in m
        or "ipblocked" in m
    )


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

            # Video description. The InnerTube player response is the reliable
            # source (videoDetails.shortDescription); yt.description scrapes the
            # watch page and frequently returns None, so use it only as fallback.
            description = ""
            try:
                description = yt.vid_info["videoDetails"]["shortDescription"] or ""
            except Exception:
                description = getattr(yt, "description", "") or ""

            result = {
                "title": yt.title,
                "channel": yt.author,
                "date": yt.publish_date.strftime("%d/%m/%Y"),
                "views": f"{yt.views:,}",
                "duration": formatted_duration,
                "subscribers": channel_info.get("subscribers", "N/A"),
                "videos": channel_info.get("videos", "N/A"),
                "description": description,
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
    def extract_subtitles(video_id: str, languages: List[str]) -> Optional[Dict]:
        """Extract subtitles in specified languages.

        Returns:
            Dict with keys 'subtitles' (List[Dict]) and 'language_code' (str), or None if extraction fails.
        """
        start_time = datetime.now()
        logger.info(f"Extracting subtitles for video ID: {video_id}")
        logger.debug(f"Attempting languages: {languages}")

        # If a recent IP block tripped the cooldown, don't touch YouTube at all —
        # skip straight to audio transcription so the IP can recover.
        if _subtitle_rate_limiter.in_cooldown():
            remaining = _subtitle_rate_limiter.cooldown_remaining()
            logger.warning(
                f"YouTube subtitle fetching paused (IP-block cooldown, "
                f"{remaining / 60:.1f} min left) — skipping to audio transcription"
            )
            return None

        try:
            ytt_api = YouTubeTranscriptApi()
            _subtitle_rate_limiter.wait()
            transcript_list = ytt_api.list(video_id)
            transcript = None
            detected_language = None

            # Detect the video's *original* spoken language from the auto-generated
            # (ASR) transcript, which YouTube tags with the language actually spoken.
            # This is independent of the caller's preferred-language list, so a
            # French video that also ships English subtitles is still detected as
            # French instead of whichever language sits first in `languages`.
            original_language = None
            first_available = None
            for transcript_item in transcript_list:
                if first_available is None:
                    first_available = transcript_item.language_code
                if transcript_item.is_generated:
                    original_language = transcript_item.language_code
                    break
            original_language = original_language or first_available
            if original_language:
                logger.info(f"Detected original spoken language: {original_language}")

            # Fetch in the original language first (read it as spoken), then fall
            # back to the caller's preferred languages.
            fetch_languages = list(languages)
            if original_language:
                fetch_languages = [original_language] + [
                    lang for lang in languages if lang != original_language
                ]

            # First, try to find manually created transcript in specified languages
            try:
                transcript = transcript_list.find_manually_created_transcript(
                    fetch_languages
                )
                detected_language = transcript.language_code
                logger.info(
                    f"Found manually created transcript in language: {detected_language}"
                )
            except:
                # If no manual transcript, try auto-generated in specified languages
                try:
                    transcript = transcript_list.find_generated_transcript(
                        fetch_languages
                    )
                    detected_language = transcript.language_code
                    logger.info(
                        f"Found auto-generated transcript in requested languages: {detected_language}"
                    )
                except:
                    # If no transcript in specified languages, try any auto-generated transcript
                    try:
                        # Get all available transcripts and find the first auto-generated one
                        for transcript_item in transcript_list:
                            if transcript_item.is_generated:
                                transcript = transcript_item
                                detected_language = transcript.language_code
                                logger.info(
                                    f"Found auto-generated transcript in language: {detected_language}"
                                )
                                break
                    except Exception as e:
                        logger.warning(
                            f"Could not find any auto-generated transcript: {str(e)}"
                        )

            if transcript is None:
                logger.error("No subtitles found (neither manual nor auto-generated)")
                return None

            # Fetch the chosen transcript in its original language. We never ask
            # YouTube to translate: the summariser reads the original-language
            # text and writes the summary in the user's language, so a translate
            # request adds nothing — and on an IP block it can't succeed anyway,
            # it just piles more requests onto an already-blocked IP. Any fetch
            # failure therefore propagates to the outer handler, which trips the
            # IP-block cooldown and lets the caller fall back to audio.
            if detected_language is None:
                detected_language = transcript.language_code
            _subtitle_rate_limiter.wait()
            result = transcript.fetch()
            kind = "auto-generated" if transcript.is_generated else "manual"
            logger.info(
                f"Successfully fetched {kind} transcript in language: "
                f"{transcript.language_code}"
            )

            # Convert FetchedTranscriptSnippet objects to dictionaries
            if result and hasattr(result[0], "start"):
                result = [
                    {
                        "start": snippet.start,
                        "duration": snippet.duration,
                        "text": snippet.text,
                    }
                    for snippet in result
                ]

            # A clean fetch means the IP is healthy again — lift any cooldown.
            _subtitle_rate_limiter.clear_cooldown()

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Successfully extracted subtitles in {duration:.2f}s (language: {detected_language})"
            )

            # Return both subtitles and detected language code. Prefer the
            # original spoken language (ASR-detected) over whichever transcript we
            # ended up fetching, so the summary language follows what the video is
            # actually in — not an alternate-language subtitle track.
            return {
                "subtitles": result,
                "language_code": original_language
                or detected_language
                or "en",  # Default to "en" if somehow None
            }
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Failed to extract subtitles after {duration:.2f}s: {str(e)}")
            # On a hard rate-limit / IP block, pause subtitle fetching process-wide
            # so subsequent ingests fall back to audio instead of piling on.
            if _is_ip_block(str(e)):
                cooldown = _subtitle_rate_limiter.trip_cooldown()
                if cooldown > 0:
                    logger.warning(
                        f"YouTube IP block detected — pausing subtitle fetching for "
                        f"{cooldown / 60:.0f} min; using audio transcription meanwhile"
                    )
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
            # Try to get channel info, but handle cases where YouTube API structure has changed
            try:
                videos_count = len(channel.videos) if hasattr(channel, "videos") else 0
                views = channel.views if hasattr(channel, "views") else 0
                result = {
                    "videos": f"{videos_count:,}",
                    "subscribers": (
                        f"{channel.subscriber_count:,}"
                        if hasattr(channel, "subscriber_count")
                        else "N/A"
                    ),
                    "total_views": f"{views:,}",
                }
            except (KeyError, AttributeError) as e:
                # Handle cases where pytube can't access certain fields due to YouTube API changes
                logger.warning(f"Could not access some channel fields: {str(e)}")
                result = {
                    "videos": "N/A",
                    "subscribers": "N/A",
                    "total_views": "N/A",
                }

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Successfully extracted channel info in {duration:.2f}s")
            return result
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.warning(
                f"Failed to extract channel info after {duration:.2f}s: {str(e)}. Continuing with default values."
            )
            # Return default values instead of empty dict to ensure video processing continues
            return {
                "videos": "N/A",
                "subscribers": "N/A",
                "total_views": "N/A",
            }
