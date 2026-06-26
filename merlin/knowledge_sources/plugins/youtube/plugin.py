"""
YouTubePlugin — knowledge source plugin for YouTube videos.

Wraps the existing extraction/summarisation pipeline and returns
a normalised IngestResult that the generic API layer can persist.
"""

import json
import re
from typing import Optional

from merlin.config import settings
from merlin.core.logging import logger
from merlin.knowledge_sources.base import (
    IngestRequest,
    IngestResult,
    KnowledgeSourcePlugin,
)
from merlin.knowledge_sources.plugins.youtube.audio_transcriber import AudioTranscriber
from merlin.knowledge_sources.plugins.youtube.extractors import (
    SubtitleExtractor,
    VideoExtractor,
)
from merlin.knowledge_sources.plugins.youtube.summarizer import VideoSummarizer

# Language code → full name mapping (used for summary language selection)
LANGUAGE_MAP = {
    "en": "english",
    "fr": "french",
    "de": "german",
    "es": "spanish",
    "it": "italian",
    "pt": "portuguese",
    "ru": "russian",
    "ja": "japanese",
    "ko": "korean",
    "zh": "chinese",
    "ar": "arabic",
    "hi": "hindi",
    "nl": "dutch",
    "pl": "polish",
    "tr": "turkish",
    "sv": "swedish",
    "da": "danish",
    "no": "norwegian",
    "fi": "finnish",
    "cs": "czech",
    "hu": "hungarian",
    "ro": "romanian",
    "el": "greek",
    "he": "hebrew",
    "th": "thai",
    "vi": "vietnamese",
    "id": "indonesian",
    "ms": "malay",
    "uk": "ukrainian",
    "ca": "catalan",
    "bg": "bulgarian",
    "hr": "croatian",
    "sk": "slovak",
    "sl": "slovenian",
    "sr": "serbian",
    "et": "estonian",
    "lv": "latvian",
    "lt": "lithuanian",
}

# Reverse of LANGUAGE_MAP (full English name → ISO code) for normalising
# Whisper's detected-language field, which Groq returns as a full name
# (e.g. "french") rather than a code.
_LANGUAGE_NAME_TO_CODE = {name: code for code, name in LANGUAGE_MAP.items()}


def _normalize_language(value: Optional[str]) -> Optional[str]:
    """Normalise a Whisper-detected language to a 2-letter ISO code.

    Accepts a full English name ("french"), an ISO code ("fr"/"fr-FR"), or None.
    Returns a known 2-letter code, or None if it can't be mapped (caller defaults).
    """
    if not value:
        return None
    v = value.strip().lower()
    if v in _LANGUAGE_NAME_TO_CODE:
        return _LANGUAGE_NAME_TO_CODE[v]
    base = v.split("-")[0].split("_")[0]
    if base in LANGUAGE_MAP:
        return base
    return None


_YT_REGEX = re.compile(
    r"(?:youtube\.com/(?:[^/\n\s]+/\S+/|(?:v|e(?:mbed)?)/"
    r"|\S*?[?&]v=)|youtu\.be/)([a-zA-Z0-9_-]{11})"
)


class YouTubePlugin(KnowledgeSourcePlugin):
    source_type = "youtube"
    display_name = "YouTube Video"
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "title": "YouTube URL"},
            "languages": {
                "type": "array",
                "items": {"type": "string"},
                "title": "Preferred languages",
                "default": ["en", "fr"],
            },
            "summary_length": {
                "type": "string",
                "enum": ["short", "long"],
                "title": "Summary length",
                "default": "short",
            },
        },
        "required": ["url"],
    }

    def __init__(self):
        self._video_extractor = VideoExtractor()
        self._subtitle_extractor = SubtitleExtractor()
        self._summarizer: Optional[VideoSummarizer] = None

    @property
    def summarizer(self) -> VideoSummarizer:
        if self._summarizer is None:
            self._summarizer = VideoSummarizer(llm=settings.llm)
        return self._summarizer

    # ------------------------------------------------------------------
    # KnowledgeSourcePlugin interface
    # ------------------------------------------------------------------

    def can_handle(self, raw_input: str) -> bool:
        return bool(_YT_REGEX.search(raw_input))

    def validate_input(self, raw_input: str, options: dict) -> list[str]:
        errors = []
        if not self.can_handle(raw_input):
            errors.append("Not a valid YouTube URL")
        length = options.get("summary_length", "short")
        if length not in ("short", "long"):
            errors.append("summary_length must be one of: short, long")
        return errors

    def ingest(self, request: IngestRequest) -> IngestResult:
        url = request.raw_input
        user_languages: list[str] = request.options.get("languages", ["en", "fr"])
        summary_length: str = request.options.get("summary_length", "short")

        request.report(5, "Extracting video ID…")
        video_id = self._video_extractor.extract_video_id(url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from: {url}")

        request.report(10, "Fetching video metadata…")
        video_info = self._video_extractor.extract_video_info(url)
        if not video_info:
            raise ValueError("Failed to fetch video metadata from YouTube")
        video_info["video_id"] = video_id
        request.set_title(video_info.get("title", ""))

        request.report(25, "Extracting subtitles…")
        subtitle_result = self._subtitle_extractor.extract_subtitles(
            video_id,
            user_languages + ["en", "fr", "de"],
        )

        # Audio seconds billed by Groq — only set when the transcription
        # fallback runs (subtitles are free); drives the transcribe cost row.
        transcribe_audio_seconds: float | None = None
        if subtitle_result:
            subtitles = subtitle_result["subtitles"]
            detected_language = subtitle_result["language_code"]
            raw_text = self._subtitle_extractor.extract_text(subtitles)
        else:
            request.report(
                35, "No subtitles found — downloading audio for transcription…"
            )
            logger.warning(
                f"No subtitles for {video_id}, falling back to audio transcription"
            )
            success, fallback_subtitles, error_msg, audio_language = (
                AudioTranscriber.transcribe_video(url)
            )
            if not success or not fallback_subtitles:
                raise ValueError(f"Failed to get subtitles or transcript: {error_msg}")
            subtitles = fallback_subtitles
            # Whisper auto-detects the spoken language — use it instead of
            # assuming English, so a French video summarises as French.
            detected_language = _normalize_language(audio_language) or "en"
            raw_text = self._subtitle_extractor.extract_text(subtitles)
            # Approximate billed audio length from the last segment's end time
            # (Groq bills by audio duration). Best-effort — never blocks ingest.
            try:
                transcribe_audio_seconds = max(
                    (s.get("start", 0) or 0) + (s.get("duration", 0) or 0)
                    for s in subtitles
                )
            except (ValueError, TypeError, AttributeError):
                transcribe_audio_seconds = None

        request.report(50, "Generating summary…")
        summary_lang = self._pick_summary_language(detected_language, user_languages)
        summary, topics, timestamps = self.summarizer.summarize(
            subtitles=raw_text,
            title=video_info["title"],
            channel=video_info["channel"],
            lang=summary_lang,
            summary_length=summary_length,
            streaming=False,
            description=video_info.get("description", ""),
        )
        # Token counts + provider-reported cost from the call just made.
        summ_usage = self.summarizer.last_usage or {}

        request.report(90, "Saving to knowledge base…")

        # Build thumbnail URL (no network call needed)
        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

        # Parse publish date
        published_at = None
        try:
            from datetime import datetime

            published_at = datetime.strptime(video_info["date"], "%d/%m/%Y")
        except Exception:
            pass

        # Parse views integer
        views = None
        try:
            views = int(video_info["views"].replace(",", "").replace(" views", ""))
        except Exception:
            pass

        return IngestResult(
            source_type="youtube",
            source_id=video_id,
            title=video_info["title"],
            author=video_info.get("channel"),
            published_at=published_at,
            raw_content=raw_text,
            summary=summary,
            summary_length=summary_length,
            tags=[],
            topics=topics,
            word_count=len(raw_text.split()),
            llm_model=settings.llm_model_name,
            summarize_input_tokens=summ_usage.get("input_tokens"),
            summarize_output_tokens=summ_usage.get("output_tokens"),
            summarize_cost_usd=summ_usage.get("cost_usd"),
            transcribe_audio_seconds=transcribe_audio_seconds,
            transcribe_model="whisper-large-v3-turbo"
            if transcribe_audio_seconds
            else None,
            source_metadata={
                "video_id": video_id,
                "channel": video_info.get("channel"),
                "views": views,
                "duration": video_info.get("duration"),
                "subscribers": video_info.get("subscribers"),
                "videos_count": video_info.get("videos"),
                "timestamps": json.dumps(timestamps),
                "detected_language": detected_language,
                "thumbnail_url": thumbnail_url,
                "description": video_info.get("description", ""),
            },
        )

    def resummarize(
        self,
        raw_text: str,
        title: str,
        channel: str | None,
        detected_language: str,
        user_languages: list[str],
        summary_length: str,
        description: str | None = None,
    ) -> tuple[str, dict, dict]:
        """Re-summarise an already-ingested video from its stored transcript.

        No subtitle/audio re-download — the transcript is already persisted, so
        this only re-runs the summariser (e.g. to change the summary length or
        language). `description` is the (possibly self-healed) video description
        the caller wants to ground the summary with. Returns
        (summary, topics, timestamps).
        """
        summary_lang = self._pick_summary_language(
            detected_language or "", user_languages
        )
        return self.summarizer.summarize(
            subtitles=raw_text,
            title=title,
            channel=channel or "",
            lang=summary_lang,
            summary_length=summary_length,
            streaming=False,
            description=description,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pick_summary_language(detected_code: str, user_languages: list[str]) -> str:
        """Pick the summary language from the languages the user understands.

        If the video's own language is one the user understands, summarise in it
        (read in the original). Otherwise summarise in the user's *preferred*
        understood language — the first in their list — never a hard-coded
        English, so the language picker actually controls the output.
        """
        if not user_languages:
            return "english"
        normalized = [lang.lower() for lang in user_languages]
        base = detected_code.split("-")[0].split("_")[0].lower()
        if base in normalized:
            return LANGUAGE_MAP.get(base, "english")
        return LANGUAGE_MAP.get(normalized[0], "english")
