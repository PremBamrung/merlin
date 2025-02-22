import argparse
import os
import re
import time
from io import BytesIO
from typing import Any, Callable, Dict, List, Optional

import pytube
import requests
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_openai.chat_models import AzureChatOpenAI, ChatOpenAI
from PIL import Image
from pytube import Channel
from pytube.innertube import InnerTube
from sqlalchemy.orm import Session
from youtube_transcript_api import YouTubeTranscriptApi

from merlin.llm.openrouter import llm
from merlin.utils import logger


class CustomPyYouTube(pytube.YouTube):
    def __init__(
        self,
        url: str,
        on_progress_callback: Optional[Callable[[Any, bytes, int], None]] = None,
        on_complete_callback: Optional[Callable[[Any, Optional[str]], None]] = None,
        proxies: Dict[str, str] = None,
        use_oauth: bool = False,
        allow_oauth_cache: bool = True,
    ):
        super().__init__(
            url,
            on_progress_callback,
            on_complete_callback,
            proxies,
            use_oauth,
            allow_oauth_cache,
        )
        self.client = "WEB"  # Force to use 'WEB' client
        self._vid_info = None  # Reset the vid_info

    @property
    def vid_info(self):
        """Parse the raw vid info and return the parsed result.

        :rtype: Dict[Any, Any]
        """
        if self._vid_info:
            return self._vid_info

        self.innertube = InnerTube(
            use_oauth=self.use_oauth,
            allow_cache=self.allow_oauth_cache,
            client=self.client,
        )
        innertube_response = self.innertube.player(self.video_id)
        self._vid_info = innertube_response
        return self._vid_info


class YouTube:
    def __init__(self):
        """Initialize YouTube class with prompt template for summarization."""
        TEMPLATE = """Given the subtitles of a Youtube video,
        Write a short summary in bullet points, extracting the main key information. Format the summary using clean and concise bullet points, highlighting the main ideas. Write the summary in {lang}
        # Video  titled "{title}" from the channel "{channel}"

        # The subtitles :{subtitles}

        # Answer: """
        self.prompt_template = PromptTemplate(
            template=TEMPLATE, input_variables=["subtitles", "lang", "title", "channel"]
        )

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """Extract the video ID from a YouTube URL."""
        regex = r"(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
        match = re.findall(regex, url)
        video_id = match[0] if match else None
        if video_id:
            logger.info(f"Successfully extracted video ID: {video_id}")
        else:
            logger.warning(f"Failed to extract video ID from URL: {url}")
        return video_id

    @staticmethod
    def extract_subtitles(
        video_id: str, languages: List[str]
    ) -> Optional[List[Dict[str, Any]]]:
        """Retrieve the subtitles of a YouTube video."""
        start_time = time.time()
        logger.info(f"Extracting subtitles for video ID: {video_id}")
        logger.debug(f"Attempting languages: {languages}")

        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            try:
                transcript = transcript_list.find_manually_created_transcript(languages)
                logger.info("Found manually created transcript")
            except:
                transcript = transcript_list.find_generated_transcript(languages)
                logger.info("Found auto-generated transcript")

            result = transcript.fetch()
            duration = time.time() - start_time
            logger.info(f"Successfully extracted subtitles in {duration:.2f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Failed to extract subtitles after {duration:.2f}s: {str(e)}")
            return None

    @staticmethod
    def extract_thumbnail(video_id: str) -> Optional[Image.Image]:
        """Retrieve the thumbnail image of a YouTube video."""
        start_time = time.time()
        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        logger.info(f"Fetching thumbnail for video ID: {video_id}")

        try:
            response = requests.get(thumbnail_url)
            image = Image.open(BytesIO(response.content))
            duration = time.time() - start_time
            logger.info(f"Successfully fetched thumbnail in {duration:.2f}s")
            return image
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Failed to fetch thumbnail after {duration:.2f}s: {str(e)}")
            return None

    def get_cached_video(
        self, video_id: str, session: Session
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached video data from database if it exists."""
        from merlin.database.models import YouTubeVideoSummary

        logger.debug(f"Checking cache for video ID: {video_id}")
        cached_video = (
            session.query(YouTubeVideoSummary).filter_by(video_id=video_id).first()
        )
        if cached_video:
            logger.info(f"Cache hit for video ID: {video_id}")
            return {
                "title": cached_video.title,
                "channel": cached_video.channel,
                "date": cached_video.date.strftime("%d/%m/%Y"),
                "views": f"{cached_video.views:,}",
                "duration": cached_video.duration,
                "subscribers": cached_video.subscribers,
                "videos": cached_video.videos,
                "summary": cached_video.summary,
                "subtitles": cached_video.subtitles,
                "words_count": cached_video.words_count,
                "video_id": cached_video.video_id,
                "cached": True,
            }
        logger.info(f"Cache miss for video ID: {video_id}")
        return None

    @staticmethod
    def extract_video_info(video_url: str) -> Optional[Dict[str, Any]]:
        """Retrieve basic information about a YouTube video."""
        start_time = time.time()
        logger.info(f"Extracting video info for URL: {video_url}")
        try:
            yt = CustomPyYouTube(video_url)

            # Format duration to hh:mm:ss
            duration = yt.length
            hours, remainder = divmod(duration, 3600)
            minutes, seconds = divmod(remainder, 60)
            formatted_duration = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

            channel_info = YouTube.extract_channel_info(yt.channel_url)

            result = {
                "title": yt.title,
                "channel": yt.author,
                "date": yt.publish_date.strftime(
                    "%d/%m/%Y"
                ),  # Format date to dd/mm/yyyy
                "views": f"{yt.views:,}",  # Format number with thousand separator
                "duration": formatted_duration,
                "subscribers": channel_info.get("subscribers", "N/A"),
                "videos": channel_info.get("videos", "N/A"),
            }
            duration = time.time() - start_time
            logger.info(f"Successfully extracted video info in {duration:.2f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Failed to extract video info after {duration:.2f}s: {str(e)}"
            )
            return None

    @staticmethod
    def extract_channel_info(channel_url: str) -> Dict[str, Any]:
        """Retrieve the channel information using PyTube."""
        start_time = time.time()
        logger.info(f"Extracting channel info for URL: {channel_url}")

        try:
            channel = Channel(channel_url)
            result = {
                # "subscribers": f"{channel.subscriber_count:,}",  # Format number with thousand separator
                "videos": f"{len(channel.videos):,}",
                "total_views": f"{channel.views:,}",
            }
            duration = time.time() - start_time
            logger.info(f"Successfully extracted channel info in {duration:.2f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Failed to extract channel info after {duration:.2f}s: {str(e)}"
            )
            return {}

    @staticmethod
    def extract_text(subtitles: List[Dict[str, Any]]) -> str:
        """Concatenate subtitles into a single text string."""
        text = " ".join([sub["text"] for sub in subtitles])
        words_count = len(text.split())
        logger.info(f"Extracted text with {words_count:,} words")
        return text

    def summarize(
        self,
        subtitles: str,
        title: str,
        channel: str,
        lang: str = "english",
        streaming: bool = False,
    ) -> str:
        """Generate a summary of the subtitles using Azure OpenAI model, incorporating video metadata."""
        start_time = time.time()
        logger.info(f"Starting summarization for video: {title}")
        logger.debug(
            f"Summarization parameters - Language: {lang}, Streaming: {streaming}"
        )

        llm_chain = self.prompt_template | llm
        summary = ""

        prompt_input = {
            "subtitles": subtitles,
            "lang": lang,
            "title": title,
            "channel": channel,
        }

        try:
            if streaming:
                logger.debug("Using streaming mode for summarization")
                for chunk in llm_chain.stream(prompt_input):
                    yield chunk.content
            else:
                summary = llm_chain.run(prompt_input)
                duration = time.time() - start_time
                logger.info(f"Summarization completed in {duration:.2f}s")
                return summary
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Summarization failed after {duration:.2f}s: {str(e)}")
            raise


if __name__ == "__main__":
    # Command-line argument parser configuration
    parser = argparse.ArgumentParser(
        description="Extract information from a YouTube video and summarize subtitles."
    )
    parser.add_argument("url", type=str, help="YouTube video URL")
    parser.add_argument(
        "--lang", default="english", help="Preferred language for the summary"
    )

    args = parser.parse_args()
    load_dotenv()

    yt = YouTube(
        azure_model_deployment=os.getenv("AZURE_MODEL_DEPLOYMENT"),
        azure_endpoint=os.getenv("AZURE_ENDPOINT"),
        azure_key=os.getenv("AZURE_KEY"),
        azure_api_version=os.getenv("AZURE_API_VERSION"),
    )

    video_id = yt.extract_video_id(args.url)
    video_info = yt.extract_video_info(args.url)

    if video_id:
        subtitles = yt.extract_subtitles(video_id, ["en", "fr", "de"])

        if subtitles:
            text = yt.extract_text(subtitles)

            if text:
                print("Subtitles extracted successfully!")
                print(f"Title: {video_info['title']}")
                print(f"Channel: {video_info['channel']}")
                print(f"Date: {video_info['date']}")
                print(f"Views: {video_info['views']}")
                print(f"Duration: {video_info['duration']}")
                print(f"Subscribers: {video_info['subscribers']}")
                print(f"Videos: {video_info['videos']}")
                print(
                    f"Words count: {len(text.split()):,}"
                )  # Format words count with thousand separator

                document = Document(page_content=text, metadata={"source": args.url})

                summary = yt.summarize(
                    subtitles=text,
                    title=video_info["title"],
                    channel=video_info["channel"],
                    lang=args.lang,
                )

                print("Summary:")
                print(summary)

                thumbnail_img = yt.extract_thumbnail(video_id)
                if thumbnail_img:
                    pass
            else:
                print("Error extracting text from subtitles.")
        else:
            print("No subtitles found for the given video URL.")
    else:
        print("Invalid YouTube video URL. Please try again.")
