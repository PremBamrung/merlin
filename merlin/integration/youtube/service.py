from typing import Dict, List, Optional

from PIL import Image

from merlin.database.manager import DatabaseManager
from merlin.database.repositories import VideoRepository
from merlin.integration.youtube.audio_transcriber import AudioTranscriber
from merlin.integration.youtube.extractors import (
    ChannelExtractor,
    SubtitleExtractor,
    VideoExtractor,
)
from merlin.integration.youtube.summarizer import VideoSummarizer
from merlin.llm.azureopenai import llm
from merlin.utils import logger

# Language code to summary language name mapping
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
    "mk": "macedonian",
    "sq": "albanian",
    "et": "estonian",
    "lv": "latvian",
    "lt": "lithuanian",
}


def map_language_code_to_summary_lang(language_code: str) -> str:
    """Map language code to summary language name.

    Args:
        language_code: Two-letter language code (e.g., "fr", "en")

    Returns:
        Summary language name (e.g., "french", "english"), defaults to "english"
    """
    # Handle language codes with variants (e.g., "en-US" -> "en")
    base_code = language_code.split("-")[0].split("_")[0].lower()
    return LANGUAGE_MAP.get(base_code, "english")


def match_video_language_to_user_languages(
    video_language_code: str, user_languages: List[str]
) -> str:
    """Match video language to user's understood languages.

    Args:
        video_language_code: Detected language code from video subtitles
        user_languages: List of language codes the user understands (e.g., ["fr", "en"])

    Returns:
        Summary language name to use (e.g., "french" if video is in French and user understands French,
        otherwise "english")
    """
    # Normalize video language code (handle variants like "en-US")
    video_base_code = video_language_code.split("-")[0].split("_")[0].lower()

    # Check if video language is in user's understood languages
    if video_base_code in [lang.lower() for lang in user_languages]:
        return map_language_code_to_summary_lang(video_base_code)
    else:
        # Default to English if no match
        return "english"


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
        """Clear cached video summary, but keep video info and subtitles.

        This allows redoing the summary without re-extracting video info and subtitles.
        """
        return self.db.execute_with_session(
            lambda session: VideoRepository.clear_video_summary_only(session, video_id)
        )

    def get_cached_video_info_and_subtitles(self, video_id: str) -> Optional[Dict]:
        """Retrieve cached video info and subtitles, even if summary doesn't exist."""
        cached = self.get_cached_video(video_id)
        if cached and cached.get("subtitles"):
            return cached
        return None

    def get_all_videos(self) -> List[Dict]:
        """Retrieve all cached video summaries."""
        return self.db.execute_with_session(VideoRepository.get_all_videos)

    def process_video(
        self,
        url: str,
        user_languages: List[str] = None,
        summary_length: str = "medium",
        streaming: bool = False,
    ) -> Optional[Dict]:
        """Process a YouTube video URL.

        Coordinates the entire video processing pipeline:
        1. Extract video ID and info
        2. Get subtitles and detect language
        3. Match video language to user's understood languages
        4. Generate summary in matched language
        5. Save to database

        Args:
            url: YouTube video URL
            user_languages: List of language codes the user understands (e.g., ["fr", "en"])
                           Defaults to ["en"] if not provided
            summary_length: Length of summary ("short", "medium", "long")
            streaming: Whether to stream the summary response

        Returns:
            Dictionary containing video information and summary,
            or None if processing fails
        """
        # Extract video ID
        if streaming:
            yield {"type": "status", "message": "Extracting video ID..."}
        video_id = self.video_extractor.extract_video_id(url)
        if not video_id:
            logger.error("Failed to extract video ID")
            if streaming:
                yield {"type": "error", "message": "Failed to extract video ID"}
            return None

        # Check for cached video info and subtitles first
        cached_data = self.get_cached_video_info_and_subtitles(video_id)
        if cached_data:
            video_info = {
                "video_id": video_id,
                "title": cached_data["title"],
                "channel": cached_data["channel"],
                "date": cached_data["date"],
                "views": cached_data["views"],
                "duration": cached_data["duration"],
                "subscribers": cached_data.get("subscribers", "N/A"),
                "videos": cached_data.get("videos", "N/A"),
            }
            text = cached_data["subtitles"]
            # Extract subtitles list from cached text (we'll need to reconstruct this)
            # For now, we'll use the text directly
            use_cached = True
            if streaming:
                yield {
                    "type": "status",
                    "message": "Using cached video info and subtitles...",
                }
        else:
            # Extract video info
            if streaming:
                yield {"type": "status", "message": "Extracting video information..."}
            video_info = self.video_extractor.extract_video_info(url)
            if not video_info:
                logger.error("Failed to extract video info")
                if streaming:
                    yield {
                        "type": "error",
                        "message": "Failed to extract video information",
                    }
                return None
            video_info["video_id"] = video_id
            use_cached = False

        # Default user languages to English if not provided
        if user_languages is None:
            user_languages = ["en"]

        if use_cached:
            # Use cached subtitles and text
            # Note: We default to "en" for language detection when using cached data
            # This could be improved by storing detected_language_code in the database
            detected_language_code = "en"  # Default, could be improved by storing this
            subtitles = None  # We have text but not subtitle list, which is fine for summarization
            logger.info(
                f"Using cached video info and subtitles for video ID: {video_id}"
            )
        else:
            # Extract subtitles
            if streaming:
                yield {"type": "status", "message": "Extracting subtitles..."}
            subtitle_result = self.subtitle_extractor.extract_subtitles(
                video_id,
                user_languages
                + ["en", "fr", "de"],  # Include common languages as fallback
            )
            if not subtitle_result:
                logger.warning(
                    "No subtitles found, attempting audio download and transcription fallback"
                )
                if streaming:
                    yield {
                        "type": "status",
                        "message": "No subtitles found. Downloading audio...",
                    }
                # Fallback: download audio and transcribe using Groq Whisper
                success, fallback_subtitles, error_msg = (
                    AudioTranscriber.transcribe_video(url)
                )
                if success and fallback_subtitles:
                    if streaming:
                        yield {
                            "type": "status",
                            "message": f"Transcribing audio... ({len(fallback_subtitles)} segments found)",
                        }
                    logger.info(
                        f"Successfully transcribed audio with {len(fallback_subtitles)} segments"
                    )
                    # For audio transcription, we don't have language detection, default to English
                    subtitle_result = {
                        "subtitles": fallback_subtitles,
                        "language_code": "en",  # Default for audio transcription
                    }
                else:
                    logger.error(
                        f"Failed to extract subtitles and audio transcription fallback failed: {error_msg}"
                    )
                    if streaming:
                        yield {
                            "type": "error",
                            "message": f"Failed to extract subtitles and audio transcription failed: {error_msg}",
                        }
                    return None

            # Extract subtitles list and detected language
            subtitles = subtitle_result["subtitles"]
            detected_language_code = subtitle_result["language_code"]

            # Convert subtitles to text
            if streaming:
                yield {"type": "status", "message": "Processing transcript..."}
            text = self.subtitle_extractor.extract_text(subtitles)
            if not text:
                logger.error("Failed to extract text from subtitles")
                if streaming:
                    yield {
                        "type": "error",
                        "message": "Failed to extract text from subtitles",
                    }
                return None

            # Save video info and subtitles immediately (before summary generation)
            # This ensures they're cached even if summary generation fails
            try:
                self.db.execute_with_session(
                    lambda session: VideoRepository.save_or_update_video_info_and_subtitles(
                        session, video_info, text
                    )
                )
                logger.info(f"Cached video info and subtitles for video ID: {video_id}")
            except Exception as e:
                logger.warning(f"Failed to cache video info and subtitles: {str(e)}")
                # Continue anyway, as this is not critical

        # Match video language to user's understood languages
        summary_lang = match_video_language_to_user_languages(
            detected_language_code, user_languages
        )
        logger.info(
            f"Video language: {detected_language_code}, User languages: {user_languages}, "
            f"Summary language: {summary_lang}"
        )

        try:
            # Generate summary with new parameters
            if streaming:
                try:
                    # First yield the metadata as a dict (include detected language info)
                    yield {
                        "type": "metadata",
                        "video_info": video_info,
                        "text": text,
                        "detected_language": detected_language_code,
                        "summary_language": summary_lang,
                    }

                    # Then stream the summary chunks
                    yield {"type": "status", "message": "Generating summary..."}
                    summary_text = ""
                    for chunk in self.summarizer.summarize(
                        subtitles=text,
                        title=video_info["title"],
                        channel=video_info["channel"],
                        lang=summary_lang,
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

                    # Get LLM model name
                    llm_model = getattr(llm, "deployment_name", None) or "unknown"

                    # Update the summary in the database (video info and subtitles already saved)
                    try:
                        self.db.execute_with_session(
                            lambda session: VideoRepository.update_video_summary_only(
                                session,
                                video_id,
                                summary_text,
                                summary_length=summary_length,
                                llm_model=llm_model,
                                topics=topics,
                                timestamps=timestamps,
                            )
                        )
                        logger.info(f"Updated summary for video ID: {video_id}")
                    except Exception as e:
                        logger.error(f"Failed to update summary in database: {str(e)}")
                        # Continue anyway

                    # Finally yield the summary metadata
                    yield {
                        "type": "summary_metadata",
                        "summary": summary_text,
                        "topics": topics,
                        "timestamps": timestamps,
                        "llm_model": llm_model,
                    }
                except Exception as e:
                    logger.error(f"Error in streaming mode: {str(e)}")
                    yield {"type": "error", "message": str(e)}
            else:
                summary, topics, timestamps = self.summarizer.summarize(
                    subtitles=text,
                    title=video_info["title"],
                    channel=video_info["channel"],
                    lang=summary_lang,
                    summary_length=summary_length,
                    streaming=False,
                )

                # Get LLM model name
                llm_model = getattr(llm, "deployment_name", None) or "unknown"

                # Update the summary in the database (video info and subtitles already saved)
                try:
                    self.db.execute_with_session(
                        lambda session: VideoRepository.update_video_summary_only(
                            session,
                            video_id,
                            summary,
                            summary_length=summary_length,
                            llm_model=llm_model,
                            topics=topics,
                            timestamps=timestamps,
                        )
                    )
                    logger.info(f"Updated summary for video ID: {video_id}")
                except Exception as e:
                    logger.error(f"Failed to update summary in database: {str(e)}")
                    # Try to save everything as fallback
                    self.db.execute_with_session(
                        lambda session: VideoRepository.save_video_summary(
                            session,
                            video_info,
                            text,
                            summary,
                            text,
                            summary_length=summary_length,
                            llm_model=llm_model,
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
