import os
import re
import tempfile
from typing import Dict, List, Optional

import requests
import yt_dlp
from dotenv import load_dotenv

from merlin.utils import logger

# Load environment variables
load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")


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

        # Configuration options for yt-dlp
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
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
    def transcribe_audio(
        audio_file_path: str,
    ) -> tuple[bool, Optional[List[Dict]], Optional[str]]:
        """Transcribes audio file using Groq Whisper API with verbose_json format.

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

        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
        }

        logger.info(f"Starting transcription for: {audio_file_path}")

        try:
            with open(audio_file_path, "rb") as audio_file:
                files = {
                    "file": audio_file,
                }
                data = {
                    "model": "whisper-large-v3-turbo",
                    "temperature": 0,
                    "response_format": "verbose_json",
                }

                response = requests.post(url, headers=headers, files=files, data=data)

                if not response.ok:
                    error_msg = (
                        f"Groq API error: {response.status_code} - {response.text}"
                    )
                    logger.error(error_msg)
                    return False, None, error_msg

                result = response.json()

                # Extract segments and convert to subtitle format
                segments = result.get("segments", [])
                if not segments:
                    # Fallback: if no segments, use the full text as a single entry
                    full_text = result.get("text", "")
                    if full_text:
                        duration = result.get("duration", 0)
                        subtitles = [
                            {"start": 0, "duration": duration, "text": full_text}
                        ]
                        logger.info(
                            "Transcription completed (single entry, no segments)"
                        )
                        return True, subtitles, None
                    else:
                        error_msg = (
                            "No text or segments found in transcription response"
                        )
                        logger.error(error_msg)
                        return False, None, error_msg

                # Convert segments to subtitle format
                subtitles = []
                for segment in segments:
                    start = segment.get("start", 0)
                    end = segment.get("end", 0)
                    text = segment.get("text", "").strip()
                    duration = end - start

                    if text:  # Only add non-empty segments
                        subtitles.append(
                            {
                                "start": start,
                                "duration": duration,
                                "text": text,
                            }
                        )

                logger.info(f"Transcription completed with {len(subtitles)} segments")
                return True, subtitles, None

        except FileNotFoundError:
            error_msg = f"Audio file not found: {audio_file_path}"
            logger.error(error_msg)
            return False, None, error_msg
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
