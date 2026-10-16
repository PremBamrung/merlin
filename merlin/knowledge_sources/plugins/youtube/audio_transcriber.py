from concurrent.futures import ThreadPoolExecutor
from functools import cache
import glob
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Callable, Dict, List, Optional

import groq
import yt_dlp

from merlin.config import settings
from merlin.core.logging import logger
from merlin.knowledge_sources.plugins.youtube.cookies import ytdlp_cookie_copy

GROQ_API_KEY = settings.groq_api_key
GROQ_MODEL = "whisper-large-v3-turbo"
# Per-request timeout; the SDK retries 429s, 5xx and connection errors with
# backoff (honouring Retry-After) up to _GROQ_MAX_RETRIES times.
_GROQ_TIMEOUT_SECONDS = 300.0
_GROQ_MAX_RETRIES = 3
# Chunks of one oversized file transcribed at once — small, to stay inside
# Groq's free-tier requests-per-minute.
_CHUNK_CONCURRENCY = 3

# A speech-sized audio stream: YouTube's ~50 kbps Opus (249) or 48 kbps AAC
# (139) instead of the ~130 kbps "bestaudio" — 2-3x less to download. It's
# re-encoded below anyway, so the higher-bitrate tracks buy nothing.
_AUDIO_FORMAT = "bestaudio[abr<=70]/bestaudio/best"
# YouTube intermittently 403s a media download that works moments later
# (a fresh extract gets fresh stream URLs), so a 403 is retried once after this.
_DOWNLOAD_RETRY_DELAY_SECONDS = 5.0

# Optional progress callback: (percent, message) — IngestRequest.report.
Report = Callable[[int, str], None]


def _noop_report(percent: int, message: str) -> None:
    pass


@cache
def _groq_client() -> groq.Groq:
    return groq.Groq(
        api_key=GROQ_API_KEY,
        timeout=_GROQ_TIMEOUT_SECONDS,
        max_retries=_GROQ_MAX_RETRIES,
    )


class AudioTranscriber:
    """Handles audio download and transcription for videos without subtitles."""

    @staticmethod
    def download_audio(video_url: str, out_dir: str) -> tuple[bool, Optional[str]]:
        """Download a speech-sized audio stream of a YouTube video into `out_dir`.

        One `extract_info(download=True)` pass (resolving the video twice made
        two round-trips and doubled yt-dlp's bot-detection exposure). The file
        is saved as-is (webm/m4a); `_to_speech_audio` re-encodes it.

        Returns:
            tuple[bool, Optional[str]]: (success, file_path or error_message)
        """
        ydl_opts = {
            "format": _AUDIO_FORMAT,
            "outtmpl": os.path.join(out_dir, "source.%(ext)s"),
            "quiet": True,  # Suppress yt-dlp output
            "noprogress": True,  # no [download] lines interleaved with the logs
        }
        cookie_copy = ytdlp_cookie_copy(out_dir)
        if cookie_copy:
            ydl_opts["cookiefile"] = cookie_copy

        logger.info(f"Starting audio download for: {video_url}")

        try:
            info, file_path = AudioTranscriber._download_with_retry(video_url, ydl_opts)

            if not file_path or not os.path.exists(file_path):
                error_msg = f"Downloaded file not found: {file_path}"
                logger.error(error_msg)
                return False, error_msg

            size_mb = os.path.getsize(file_path) / 1_048_576
            logger.info(
                f"Downloaded audio ({info.get('format_id')}, {size_mb:.1f} MB) "
                f"for: {info.get('title', video_url)}"
            )
            return True, file_path

        except yt_dlp.utils.DownloadError as e:
            if "403" in str(e):
                # yt-dlp's raw "unable to download video data" hides the two
                # usual causes; name them so the task error is actionable.
                hint = "" if cookie_copy else " Setting YOUTUBE_COOKIES_FILE may help."
                error_msg = (
                    "YouTube refused the audio download (HTTP 403). yt-dlp "
                    f"{yt_dlp.version.__version__} may be outdated (update and "
                    "rebuild), or YouTube is blocking this server." + hint
                )
            else:
                error_msg = f"Error during download: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"An unexpected error occurred during download: {e}"
            logger.error(error_msg)
            return False, error_msg
        finally:
            if cookie_copy:
                Path(cookie_copy).unlink(missing_ok=True)

    @staticmethod
    def _download_with_retry(video_url: str, ydl_opts: dict) -> tuple[dict, str]:
        """One yt-dlp download; an HTTP 403 is retried once after a short pause.

        Raises the last DownloadError when the retry fails too.
        """
        for attempt in (1, 2):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=True)
                    downloads = info.get("requested_downloads") or [{}]
                    file_path = downloads[0].get("filepath") or ydl.prepare_filename(
                        info
                    )
                return info, file_path
            except yt_dlp.utils.DownloadError as e:
                if attempt == 2 or "403" not in str(e):
                    raise
                logger.warning(
                    f"YouTube refused the audio download (HTTP 403) — retrying in "
                    f"{_DOWNLOAD_RETRY_DELAY_SECONDS:.0f}s: {video_url}"
                )
                time.sleep(_DOWNLOAD_RETRY_DELAY_SECONDS)
        raise AssertionError("unreachable")

    @staticmethod
    def _to_speech_audio(source_path: str, out_dir: str) -> str:
        """Re-encode to 16 kHz mono Opus at 24 kbps (Ogg) for Whisper.

        Whisper resamples to 16 kHz mono internally, so this loses nothing it
        would use, and ~24 kbps Opus keeps ~2.3 h of speech under Groq's 25 MB
        upload cap — chunking rarely kicks in. Raises CalledProcessError.
        """
        out_path = os.path.join(out_dir, "speech.ogg")
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            source_path,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "libopus",
            "-b:a",
            "24k",
            "-application",
            "voip",
            out_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return out_path

    @staticmethod
    def _result_to_subtitles(result: Dict, offset: float = 0.0) -> List[Dict]:
        """Convert a Groq verbose_json result to our subtitle format.

        `offset` (seconds) is added to every start time so transcripts from
        later audio chunks line up on the original timeline.
        """
        segments = result.get("segments", [])
        if not segments:
            full_text = (result.get("text") or "").strip()
            if not full_text:
                return []
            return [
                {
                    "start": offset,
                    "duration": result.get("duration", 0),
                    "text": full_text,
                }
            ]

        subtitles = []
        for segment in segments:
            start = segment.get("start", 0)
            end = segment.get("end", 0)
            text = segment.get("text", "").strip()
            if text:  # Only add non-empty segments
                subtitles.append(
                    {
                        "start": start + offset,
                        "duration": end - start,
                        "text": text,
                    }
                )
        return subtitles

    @staticmethod
    def _post_audio(audio_file_path: str) -> tuple[bool, Optional[Dict], Optional[str]]:
        """Send a single audio file to Groq and return the verbose_json result."""
        try:
            with open(audio_file_path, "rb") as audio_file:
                # Bytes, not the handle: a retried request must re-send the body.
                payload = (os.path.basename(audio_file_path), audio_file.read())
            result = _groq_client().audio.transcriptions.create(
                file=payload,
                model=GROQ_MODEL,
                temperature=0,
                response_format="verbose_json",
            )
        except groq.APIStatusError as e:
            if e.status_code == 413:
                error_msg = (
                    "Audio too large for Groq transcription (HTTP 413). Lower "
                    "settings.groq_max_upload_mb or shorten the video."
                )
            else:
                error_msg = f"Groq API error: {e.status_code} - {e.message}"
            logger.error(error_msg)
            return False, None, error_msg
        except groq.APIConnectionError as e:  # includes APITimeoutError
            error_msg = f"Groq request failed after retries: {e}"
            logger.error(error_msg)
            return False, None, error_msg

        return True, result.to_dict(), None

    @staticmethod
    def _split_audio(audio_file_path: str, out_dir: str) -> List[str]:
        """Split audio into time segments with ffmpeg (stream copy, no re-encode)."""
        ext = os.path.splitext(audio_file_path)[1] or ".ogg"
        out_template = os.path.join(out_dir, f"chunk_%03d{ext}")
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            audio_file_path,
            "-f",
            "segment",
            "-segment_time",
            str(settings.groq_audio_chunk_seconds),
            "-c",
            "copy",
            out_template,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return sorted(glob.glob(os.path.join(out_dir, f"chunk_*{ext}")))

    @staticmethod
    def _transcribe_chunked(
        audio_file_path: str,
        report: Report = _noop_report,
    ) -> tuple[bool, Optional[List[Dict]], Optional[str], Optional[str]]:
        """Split an oversized audio file, transcribe the chunks, and stitch.

        Chunks are transcribed concurrently (`_CHUNK_CONCURRENCY` at a time)
        and stitched in order afterwards.

        Returns (success, subtitles, error_msg, language) — language is the
        Whisper-detected language of the first chunk (the whole video is one
        language), or None if Whisper didn't report it.
        """
        chunk_dir = tempfile.mkdtemp(prefix="groq_chunks_")
        try:
            chunk_paths = AudioTranscriber._split_audio(audio_file_path, chunk_dir)
            if not chunk_paths:
                return (
                    False,
                    None,
                    "Failed to split audio for chunked transcription",
                    None,
                )

            logger.info(f"Transcribing {len(chunk_paths)} audio chunks")
            report(42, f"Transcribing audio in {len(chunk_paths)} chunks…")
            with ThreadPoolExecutor(max_workers=_CHUNK_CONCURRENCY) as pool:
                results = list(pool.map(AudioTranscriber._post_audio, chunk_paths))

            all_subtitles: List[Dict] = []
            language: Optional[str] = None
            offset = 0.0
            for i, (ok, result, error_msg) in enumerate(results):
                if not ok:
                    return (
                        False,
                        None,
                        (f"Chunk {i + 1}/{len(chunk_paths)} failed: {error_msg}"),
                        None,
                    )
                if language is None:
                    language = result.get("language")
                all_subtitles.extend(
                    AudioTranscriber._result_to_subtitles(result, offset)
                )
                # Advance the timeline by this chunk's real duration when Groq
                # reports it, else fall back to the configured chunk length.
                offset += float(
                    result.get("duration") or settings.groq_audio_chunk_seconds
                )

            if not all_subtitles:
                return False, None, "No transcription produced from audio chunks", None

            logger.info(
                f"Chunked transcription completed with {len(all_subtitles)} segments"
            )
            return True, all_subtitles, None, language
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", "replace") if e.stderr else ""
            error_msg = f"ffmpeg failed to split audio: {stderr}"
            logger.error(error_msg)
            return False, None, error_msg, None
        finally:
            shutil.rmtree(chunk_dir, ignore_errors=True)

    @staticmethod
    def transcribe_audio(
        audio_file_path: str,
        report: Report = _noop_report,
    ) -> tuple[bool, Optional[List[Dict]], Optional[str], Optional[str]]:
        """Transcribes audio file using Groq Whisper API with verbose_json format.

        Files larger than `settings.groq_max_upload_mb` are split into chunks
        and transcribed separately (Groq rejects oversized uploads with 413).

        Whisper auto-detects the spoken language (no language is forced); the
        detected language is returned so the caller can summarise accordingly
        instead of assuming English.

        Args:
            audio_file_path (str): Path to the audio file to transcribe.
            report: optional (percent, message) progress callback.

        Returns:
            tuple[bool, Optional[List[Dict]], Optional[str], Optional[str]]:
                (success, subtitles_list, error_message, language)
                subtitles_list format: [{"start": float, "duration": float, "text": str}]
                language: Whisper-detected language (raw, e.g. "english"/"fr"), or None.
        """
        if not GROQ_API_KEY:
            error_msg = "GROQ_API_KEY not found in environment variables"
            logger.error(error_msg)
            return False, None, error_msg, None

        logger.info(f"Starting transcription for: {audio_file_path}")

        try:
            size_bytes = os.path.getsize(audio_file_path)
        except OSError:
            error_msg = f"Audio file not found: {audio_file_path}"
            logger.error(error_msg)
            return False, None, error_msg, None

        max_bytes = int(settings.groq_max_upload_mb * 1024 * 1024)
        if size_bytes > max_bytes:
            logger.info(
                f"Audio is {size_bytes / 1_048_576:.1f} MB (> "
                f"{settings.groq_max_upload_mb} MB) — using chunked transcription"
            )
            return AudioTranscriber._transcribe_chunked(audio_file_path, report)

        report(42, "Transcribing audio…")
        try:
            ok, result, error_msg = AudioTranscriber._post_audio(audio_file_path)
            if not ok:
                return False, None, error_msg, None

            subtitles = AudioTranscriber._result_to_subtitles(result)
            if not subtitles:
                error_msg = "No text or segments found in transcription response"
                logger.error(error_msg)
                return False, None, error_msg, None

            language = result.get("language")
            logger.info(
                f"Transcription completed with {len(subtitles)} segments "
                f"(detected language: {language or 'unknown'})"
            )
            return True, subtitles, None, language
        except Exception as e:
            error_msg = f"An unexpected error occurred during transcription: {e}"
            logger.error(error_msg)
            return False, None, error_msg, None

    @staticmethod
    def transcribe_video(
        video_id: str,
        report: Optional[Report] = None,
    ) -> tuple[bool, Optional[List[Dict]], Optional[str], Optional[str]]:
        """Downloads a video's audio and transcribes it.

        Everything lives in a private temp directory (removed afterwards), so
        concurrent ingest workers can never pick up each other's files.

        Args:
            video_id (str): The YouTube video id. The canonical watch URL is
                built from it, dropping tracking/position params (`&pp=`, `&t=`).
            report: optional (percent, message) progress callback — the
                download / re-encode / transcribe steps report at 36–42%.

        Returns:
            tuple[bool, Optional[List[Dict]], Optional[str], Optional[str]]:
                (success, subtitles_list, error_message, language)
                subtitles_list format: [{"start": float, "duration": float, "text": str}]
                language: Whisper-detected language (raw, e.g. "english"/"fr"), or None.
        """
        report = report or _noop_report
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        work_dir = tempfile.mkdtemp(prefix=f"yt_audio_{video_id}_")
        logger.info(f"Starting video transcription for: {video_url}")

        try:
            report(36, "Downloading audio…")
            success, result = AudioTranscriber.download_audio(video_url, work_dir)
            if not success:
                return False, None, result, None  # result contains error message

            report(40, "Re-encoding audio…")
            try:
                speech_path = AudioTranscriber._to_speech_audio(result, work_dir)
            except subprocess.CalledProcessError as e:
                stderr = e.stderr.decode("utf-8", "replace") if e.stderr else ""
                error_msg = f"ffmpeg failed to re-encode audio: {stderr}"
                logger.error(error_msg)
                return False, None, error_msg, None
            Path(result).unlink(missing_ok=True)
            logger.info(
                f"Re-encoded to speech audio "
                f"({os.path.getsize(speech_path) / 1_048_576:.1f} MB)"
            )

            return AudioTranscriber.transcribe_audio(speech_path, report)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
