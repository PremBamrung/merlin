from datetime import datetime
from io import BytesIO
import re
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from PIL import Image
import pytube
from pytube import Channel
from pytube.innertube import InnerTube
import requests
from youtube_transcript_api import YouTubeTranscriptApi

from merlin.config import settings
from merlin.core.logging import logger
from merlin.core.rate_limit import MinIntervalRateLimiter
from merlin.knowledge_sources.plugins.youtube.cookies import transcript_http_client

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


# A few very common function words per language — enough to tell which
# language a video title/description is written in, without a dependency.
_STOPWORDS = {
    lang: set(words.split())
    for lang, words in {
        "en": "the and of to is in how why what with for you this your are my on it",
        "fr": "le la les des du un une et est en sur pour avec dans pas que qui ce "
        "mon je vous au aux de",
        "de": "der die das und ist ein eine mit für nicht auf ich wie zu den dem",
        "es": "el los las y es un una con para por que del como mi en de la",
        "it": "il lo gli e è un una con per che del della come non di la",
        "pt": "o os as e é um uma com para que do da como não em de no na",
    }.items()
}


def _guess_text_language(text: str) -> str | None:
    """Best-effort base language code of `text` from stop-word hits.

    Returns None unless one language clearly leads (at least two hits and
    strictly more than any other), so a short or mixed title never decides.
    """
    words = re.findall(r"[^\W\d_]+", (text or "").lower())
    scores = sorted(
        (sum(1 for w in words if w in stop), lang) for lang, stop in _STOPWORDS.items()
    )
    (runner_up, _), (best_score, best) = scores[-2], scores[-1]
    if best_score >= 2 and best_score > runner_up:
        return best
    return None


def _base_lang(code: str) -> str:
    return code.split("-")[0].split("_")[0].lower()


def _is_dub_track(track) -> bool:
    """Whether an ASR track transcribes one of YouTube's AI-dubbed audio tracks.

    Dub tracks' caption URLs carry `variant=timing-optimized`; the original
    audio's has no variant or `variant=gemini`. The URL is a private attribute
    of youtube-transcript-api, so read it defensively — if it ever goes away
    this returns False and the caller's other rules take over.
    """
    url = getattr(track, "_url", None)
    if not isinstance(url, str):
        return False
    return parse_qs(urlparse(url).query).get("variant") == ["timing-optimized"]


def _pick_original_language(tracks: list, hint_text: str = "") -> str | None:
    """Choose the video's spoken language from its caption tracks.

    The auto-generated (ASR) track carries the spoken language. A video that
    YouTube has AI-dubbed has one ASR track *per audio track* — up to ~20 — so
    in order: drop the dub tracks (`_is_dub_track`); then prefer bare codes
    ("fr") over region-tagged ones ("en-US", which dubs used to be tagged
    with); then let the language the title / description is written in break
    any tie. With no ASR track at all, the first listed track (manual tracks
    come first) is the best guess.
    """
    generated = [t for t in tracks if t.is_generated]
    if not generated:
        return tracks[0].language_code if tracks else None
    generated = [t for t in generated if not _is_dub_track(t)] or generated
    bare = [t for t in generated if "-" not in t.language_code]
    candidates = bare or generated
    if len(candidates) > 1:
        guess = _guess_text_language(hint_text)
        matching = [t for t in candidates if _base_lang(t.language_code) == guess]
        candidates = matching or candidates
    return candidates[0].language_code


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
    def extract_subtitles(
        video_id: str, languages: List[str], hint_text: str = ""
    ) -> Optional[Dict]:
        """Extract subtitles in specified languages.

        `hint_text` (title + description) breaks ties when several
        auto-generated tracks could be the original — see
        `_pick_original_language`.

        Returns:
            Dict with keys 'subtitles' (List[Dict]), 'language_code' (str, the
            spoken language), 'transcript_language' (code of the track fetched)
            and 'transcript_source' ("manual" | "auto"), or None if extraction
            fails.
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
            ytt_api = YouTubeTranscriptApi(http_client=transcript_http_client())
            _subtitle_rate_limiter.wait()
            transcript_list = ytt_api.list(video_id)
            transcript = None
            detected_language = None

            # Detect the video's *original* spoken language from the auto-generated
            # (ASR) transcript, which YouTube tags with the language actually spoken.
            # This is independent of the caller's preferred-language list, so a
            # French video that also ships English subtitles is still detected as
            # French instead of whichever language sits first in `languages`.
            original_language = _pick_original_language(
                list(transcript_list), hint_text
            )
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
                "transcript_language": transcript.language_code,
                "transcript_source": "auto" if transcript.is_generated else "manual",
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
