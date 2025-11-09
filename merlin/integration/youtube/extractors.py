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
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.list(video_id)
            transcript = None

            # First, try to find manually created transcript in specified languages
            try:
                transcript = transcript_list.find_manually_created_transcript(languages)
                logger.info("Found manually created transcript")
            except:
                # If no manual transcript, try auto-generated in specified languages
                try:
                    transcript = transcript_list.find_generated_transcript(languages)
                    logger.info(
                        "Found auto-generated transcript in requested languages"
                    )
                except:
                    # If no transcript in specified languages, try any auto-generated transcript
                    try:
                        # Get all available transcripts and find the first auto-generated one
                        for transcript_item in transcript_list:
                            if transcript_item.is_generated:
                                transcript = transcript_item
                                logger.info(
                                    f"Found auto-generated transcript in language: {transcript.language_code}"
                                )
                                break
                    except Exception as e:
                        logger.warning(
                            f"Could not find any auto-generated transcript: {str(e)}"
                        )

            if transcript is None:
                logger.error("No subtitles found (neither manual nor auto-generated)")
                return None

            # For auto-generated transcripts, try to fetch directly in whatever language they're in
            # Only translate if direct fetch fails (some auto-generated transcripts require translation)
            if transcript.is_generated:
                transcript_lang = transcript.language_code
                logger.info(
                    f"Found auto-generated transcript in language: {transcript_lang}"
                )

                # Always try direct fetch first, regardless of language
                try:
                    result = transcript.fetch()
                    logger.info(
                        f"Successfully fetched auto-generated transcript in {transcript_lang}"
                    )
                except Exception as fetch_error:
                    # If direct fetch fails, try translation (some auto-generated transcripts must be translated)
                    logger.info(
                        f"Direct fetch failed for {transcript_lang}, attempting translation"
                    )
                    target_lang = (
                        "en"
                        if "en" in languages
                        else (languages[0] if languages else "en")
                    )

                    try:
                        translated_transcript = transcript.translate(target_lang)
                        result = translated_transcript.fetch()
                        logger.info(
                            f"Successfully fetched translated transcript in {target_lang}"
                        )
                    except Exception as translate_error:
                        error_msg = str(translate_error).lower()
                        # If rate limited or translation fails, try English as fallback
                        if target_lang != "en":
                            try:
                                logger.info("Trying translation to English as fallback")
                                translated_transcript = transcript.translate("en")
                                result = translated_transcript.fetch()
                                logger.info(
                                    "Successfully fetched transcript translated to English"
                                )
                            except Exception as en_error:
                                # If all translation attempts fail, try other available auto-generated transcripts
                                if (
                                    "429" in error_msg
                                    or "too many requests" in error_msg
                                ):
                                    logger.warning(
                                        "Rate limited, trying alternative auto-generated transcripts"
                                    )
                                    try:
                                        for alt_transcript in transcript_list:
                                            if (
                                                alt_transcript.is_generated
                                                and alt_transcript.language_code
                                                != transcript_lang
                                            ):
                                                try:
                                                    result = alt_transcript.fetch()
                                                    logger.info(
                                                        f"Successfully fetched alternative transcript in {alt_transcript.language_code}"
                                                    )
                                                    break
                                                except:
                                                    continue
                                        else:
                                            logger.error(
                                                f"All attempts failed. Last error: {str(en_error)}"
                                            )
                                            raise fetch_error
                                    except Exception as alt_error:
                                        logger.error(
                                            f"Failed to find alternative transcript: {str(alt_error)}"
                                        )
                                        raise fetch_error
                                else:
                                    logger.error(
                                        f"All translation attempts failed. Last error: {str(en_error)}"
                                    )
                                    raise fetch_error
                        else:
                            logger.error(f"Translation failed: {str(translate_error)}")
                            raise fetch_error
            else:
                # Manual transcript - fetch directly
                result = transcript.fetch()
                logger.info("Successfully fetched manual transcript")

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
