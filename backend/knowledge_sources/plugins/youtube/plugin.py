"""
YouTubePlugin — knowledge source plugin for YouTube videos.

Wraps the existing extraction/summarisation pipeline and returns
a normalised IngestResult that the generic API layer can persist.
"""

import json
import re
from typing import Optional

from backend.config import settings
from backend.core.logging import logger
from backend.knowledge_sources.base import (
    IngestRequest,
    IngestResult,
    KnowledgeSourcePlugin,
)
from backend.knowledge_sources.plugins.youtube.audio_transcriber import AudioTranscriber
from backend.knowledge_sources.plugins.youtube.extractors import (
    SubtitleExtractor,
    VideoExtractor,
)
from backend.knowledge_sources.plugins.youtube.summarizer import VideoSummarizer

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
                "enum": ["short", "medium", "long"],
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
        if length not in ("short", "medium", "long"):
            errors.append("summary_length must be one of: short, medium, long")
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

        request.report(25, "Extracting subtitles…")
        subtitle_result = self._subtitle_extractor.extract_subtitles(
            video_id,
            user_languages + ["en", "fr", "de"],
        )

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
            success, fallback_subtitles, error_msg = AudioTranscriber.transcribe_video(
                url
            )
            if not success or not fallback_subtitles:
                raise ValueError(f"Failed to get subtitles or transcript: {error_msg}")
            subtitles = fallback_subtitles
            detected_language = "en"
            raw_text = self._subtitle_extractor.extract_text(subtitles)

        request.report(50, "Generating summary…")
        summary_lang = self._pick_summary_language(detected_language, user_languages)
        summary, topics, timestamps = self.summarizer.summarize(
            subtitles=raw_text,
            title=video_info["title"],
            channel=video_info["channel"],
            lang=summary_lang,
            summary_length=summary_length,
            streaming=False,
        )

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
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pick_summary_language(detected_code: str, user_languages: list[str]) -> str:
        if not user_languages:
            return "english"
        base = detected_code.split("-")[0].split("_")[0].lower()
        if base in [lang.lower() for lang in user_languages]:
            return LANGUAGE_MAP.get(base, "english")
        return "english"
