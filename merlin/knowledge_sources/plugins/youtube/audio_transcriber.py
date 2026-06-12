import glob
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional

from dotenv import load_dotenv
import requests
import yt_dlp

from merlin.config import settings
from merlin.core.logging import logger

GROQ_API_KEY = settings.groq_api_key
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


class AudioTranscriber:
    """Handles audio download and transcription for videos without subtitles."""

    @staticmethod
    def download_audio(video_url: str, output_path: str) -> tuple[bool, Optional[str]]:
        """Downloads the best audio from a given YouTube URL and saves it as an MP3 file.

        Args:
            video_url (str): The URL of the YouTube video.
            output_path (str): The output template for the filename.

        Returns:
            tuple[bool, Optional[str]]: (success, file_path or error_message)
        """
        actual_file_path = None

        # Callback to capture the actual file path
        def progress_hook(d):
            nonlocal actual_file_path
            if d["status"] == "finished":
                filename = d.get("filename", "")
                if filename:
                    # The filename will be the base name, but postprocessor adds .mp3
                    # So we need to replace the extension
                    base_name = os.path.splitext(filename)[0]
                    actual_file_path = f"{base_name}.mp3"

        # Configuration options for yt-dlp.
        # Whisper resamples to 16 kHz mono internally, so downmixing here is
        # lossless for transcription and shrinks the file ~5x (a 192 kbps stereo
        # MP3 hits Groq's 25 MB upload cap around ~17 min; 16 kHz mono @ 64 kbps
        # pushes that past ~50 min, with chunking covering anything longer).
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "64",
                }
            ],
            "postprocessor_args": ["-ar", "16000", "-ac", "1"],
            "outtmpl": output_path,
            "quiet": True,  # Suppress yt-dlp output
            "progress_hooks": [progress_hook],
        }

        logger.info(f"Starting audio download for: {video_url}")

        try:
            # Create a YoutubeDL object with the specified options
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info first to get video title
                info = ydl.extract_info(video_url, download=False)
                title = info.get("title", "audio")

                # Download the audio
                ydl.download([video_url])

            # If callback didn't set the path, construct it from the template
            if not actual_file_path:
                # Sanitize title for filesystem use
                sanitized_title = re.sub(r'[<>:"/\\|?*]', "_", title)
                # Replace template variables
                actual_file_path = output_path.replace(
                    "%(title)s", sanitized_title
                ).replace("%(ext)s", "mp3")

            # Verify file exists
            if not os.path.exists(actual_file_path):
                # Try to find the file in the same directory
                base_dir = os.path.dirname(actual_file_path) or "."
                if os.path.exists(base_dir):
                    mp3_files = [f for f in os.listdir(base_dir) if f.endswith(".mp3")]
                    if mp3_files:
                        # Get the most recently modified one
                        actual_file_path = os.path.join(
                            base_dir,
                            max(
                                mp3_files,
                                key=lambda f: os.path.getmtime(
                                    os.path.join(base_dir, f)
                                ),
                            ),
                        )

            if not os.path.exists(actual_file_path):
                error_msg = f"Downloaded file not found: {actual_file_path}"
                logger.error(error_msg)
                return False, error_msg

            logger.info(f"Successfully downloaded audio to: {actual_file_path}")
            return True, actual_file_path

        except yt_dlp.utils.DownloadError as e:
            error_msg = f"Error during download: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"An unexpected error occurred during download: {e}"
            logger.error(error_msg)
            return False, error_msg

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
        """POST a single audio file to Groq and return the parsed JSON result."""
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        with open(audio_file_path, "rb") as audio_file:
            files = {"file": audio_file}
            data = {
                "model": "whisper-large-v3-turbo",
                "temperature": 0,
                "response_format": "verbose_json",
            }
            response = requests.post(GROQ_URL, headers=headers, files=files, data=data)

        if not response.ok:
            if response.status_code == 413:
                error_msg = (
                    "Audio too large for Groq transcription (HTTP 413). Lower "
                    "settings.groq_max_upload_mb or shorten the video."
                )
            else:
                error_msg = f"Groq API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return False, None, error_msg

        return True, response.json(), None

    @staticmethod
    def _split_audio(audio_file_path: str, out_dir: str) -> List[str]:
        """Split audio into time segments with ffmpeg (stream copy, no re-encode)."""
        out_template = os.path.join(out_dir, "chunk_%03d.mp3")
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
        return sorted(glob.glob(os.path.join(out_dir, "chunk_*.mp3")))

    @staticmethod
    def _transcribe_chunked(
        audio_file_path: str,
    ) -> tuple[bool, Optional[List[Dict]], Optional[str]]:
        """Split an oversized audio file, transcribe each chunk, and stitch."""
        chunk_dir = tempfile.mkdtemp(prefix="groq_chunks_")
        try:
            chunk_paths = AudioTranscriber._split_audio(audio_file_path, chunk_dir)
            if not chunk_paths:
                return False, None, "Failed to split audio for chunked transcription"

            logger.info(f"Transcribing {len(chunk_paths)} audio chunks")
            all_subtitles: List[Dict] = []
            offset = 0.0
            for i, chunk_path in enumerate(chunk_paths):
                ok, result, error_msg = AudioTranscriber._post_audio(chunk_path)
                if not ok:
                    return (
                        False,
                        None,
                        (f"Chunk {i + 1}/{len(chunk_paths)} failed: {error_msg}"),
                    )
                all_subtitles.extend(
                    AudioTranscriber._result_to_subtitles(result, offset)
                )
                # Advance the timeline by this chunk's real duration when Groq
                # reports it, else fall back to the configured chunk length.
                offset += float(
                    result.get("duration") or settings.groq_audio_chunk_seconds
                )

            if not all_subtitles:
                return False, None, "No transcription produced from audio chunks"

            logger.info(
                f"Chunked transcription completed with {len(all_subtitles)} segments"
            )
            return True, all_subtitles, None
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", "replace") if e.stderr else ""
            error_msg = f"ffmpeg failed to split audio: {stderr}"
            logger.error(error_msg)
            return False, None, error_msg
        finally:
            shutil.rmtree(chunk_dir, ignore_errors=True)

    @staticmethod
    def transcribe_audio(
        audio_file_path: str,
    ) -> tuple[bool, Optional[List[Dict]], Optional[str]]:
        """Transcribes audio file using Groq Whisper API with verbose_json format.

        Files larger than `settings.groq_max_upload_mb` are split into chunks
        and transcribed separately (Groq rejects oversized uploads with 413).

        Args:
            audio_file_path (str): Path to the audio file to transcribe.

        Returns:
            tuple[bool, Optional[List[Dict]], Optional[str]]:
                (success, subtitles_list, error_message)
                subtitles_list format: [{"start": float, "duration": float, "text": str}]
        """
        if not GROQ_API_KEY:
            error_msg = "GROQ_API_KEY not found in environment variables"
            logger.error(error_msg)
            return False, None, error_msg

        logger.info(f"Starting transcription for: {audio_file_path}")

        try:
            size_bytes = os.path.getsize(audio_file_path)
        except OSError:
            error_msg = f"Audio file not found: {audio_file_path}"
            logger.error(error_msg)
            return False, None, error_msg

        max_bytes = int(settings.groq_max_upload_mb * 1024 * 1024)
        if size_bytes > max_bytes:
            logger.info(
                f"Audio is {size_bytes / 1_048_576:.1f} MB (> "
                f"{settings.groq_max_upload_mb} MB) — using chunked transcription"
            )
            return AudioTranscriber._transcribe_chunked(audio_file_path)

        try:
            ok, result, error_msg = AudioTranscriber._post_audio(audio_file_path)
            if not ok:
                return False, None, error_msg

            subtitles = AudioTranscriber._result_to_subtitles(result)
            if not subtitles:
                error_msg = "No text or segments found in transcription response"
                logger.error(error_msg)
                return False, None, error_msg

            logger.info(f"Transcription completed with {len(subtitles)} segments")
            return True, subtitles, None
        except Exception as e:
            error_msg = f"An unexpected error occurred during transcription: {e}"
            logger.error(error_msg)
            return False, None, error_msg

    @staticmethod
    def transcribe_video(
        video_url: str,
    ) -> tuple[bool, Optional[List[Dict]], Optional[str]]:
        """Downloads audio from video URL and transcribes it.

        Args:
            video_url (str): The URL of the YouTube video.

        Returns:
            tuple[bool, Optional[List[Dict]], Optional[str]]:
                (success, subtitles_list, error_message)
                subtitles_list format: [{"start": float, "duration": float, "text": str}]
        """
        # Create a temporary file for the audio
        temp_dir = tempfile.gettempdir()
        temp_file_template = os.path.join(temp_dir, "yt_audio_%(title)s.%(ext)s")

        logger.info(f"Starting video transcription for: {video_url}")

        # Download audio
        success, result = AudioTranscriber.download_audio(video_url, temp_file_template)
        if not success:
            return False, None, result  # result contains error message

        audio_file_path = result  # result contains the file path on success

        try:
            # Transcribe audio
            transcribe_success, subtitles, error_msg = (
                AudioTranscriber.transcribe_audio(audio_file_path)
            )

            return transcribe_success, subtitles, error_msg

        finally:
            # Clean up temporary audio file
            try:
                if os.path.exists(audio_file_path):
                    os.remove(audio_file_path)
                    logger.info(f"Cleaned up temporary audio file: {audio_file_path}")
            except Exception as e:
                logger.warning(
                    f"Failed to clean up temporary file {audio_file_path}: {e}"
                )
