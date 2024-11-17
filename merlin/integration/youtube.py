import argparse
import os
import re
from io import BytesIO
from typing import Any, Callable, Dict, List, Optional

import pytube
import requests
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_openai.chat_models import AzureChatOpenAI
from PIL import Image
from pytube import Channel
from pytube.innertube import InnerTube
from youtube_transcript_api import YouTubeTranscriptApi


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
    def __init__(
        self,
        azure_model_deployment: str,
        azure_endpoint: str,
        azure_key: str,
        azure_api_version: str,
    ):
        self.azure_model_deployment = azure_model_deployment
        self.azure_endpoint = azure_endpoint
        self.azure_key = azure_key
        self.azure_api_version = azure_api_version
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
        return match[0] if match else None

    @staticmethod
    def extract_subtitles(
        video_id: str, languages: List[str]
    ) -> Optional[List[Dict[str, Any]]]:
        """Retrieve the subtitles of a YouTube video."""
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            try:
                transcript = transcript_list.find_manually_created_transcript(languages)
            except:
                transcript = transcript_list.find_generated_transcript(languages)

            return transcript.fetch()
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    @staticmethod
    def extract_thumbnail(video_id: str) -> Optional[Image.Image]:
        """Retrieve the thumbnail image of a YouTube video."""
        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        try:
            response = requests.get(thumbnail_url)
            return Image.open(BytesIO(response.content))
        except Exception as e:
            print("Error displaying thumbnail:", e)
            return None

    @staticmethod
    def extract_video_info(video_url: str) -> Optional[Dict[str, Any]]:
        """Retrieve basic information about a YouTube video."""
        try:
            yt = CustomPyYouTube(video_url)

            # Format duration to hh:mm:ss
            duration = yt.length
            hours, remainder = divmod(duration, 3600)
            minutes, seconds = divmod(remainder, 60)
            formatted_duration = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

            channel_info = YouTube.extract_channel_info(yt.channel_url)

            return {
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
        except Exception as e:
            print(e)
            return None

    @staticmethod
    def extract_channel_info(channel_url: str) -> Dict[str, Any]:
        """Retrieve the channel information using PyTube."""
        try:
            channel = Channel(channel_url)
            return {
                # "subscribers": f"{channel.subscriber_count:,}",  # Format number with thousand separator
                "videos": f"{len(channel.videos):,}",
                "total_views": f"{channel.views:,}",
            }
        except Exception as e:
            print(f"Error retrieving channel information: {e}")
            return {}

    @staticmethod
    def extract_text(subtitles: List[Dict[str, Any]]) -> str:
        """Concatenate subtitles into a single text string."""
        return " ".join([sub["text"] for sub in subtitles])

    def summarize(
        self,
        subtitles: str,
        title: str,
        channel: str,
        lang: str = "english",
        streaming: bool = False,
    ) -> str:
        """Generate a summary of the subtitles using Azure OpenAI model, incorporating video metadata."""
        llm = AzureChatOpenAI(
            azure_endpoint=self.azure_endpoint,
            api_key=self.azure_key,
            temperature=0.01,
            max_tokens=None,
            openai_api_version=self.azure_api_version,
            deployment_name=self.azure_model_deployment,
            streaming=streaming,
        )
        llm_chain = self.prompt_template | llm
        summary = ""

        prompt_input = {
            "subtitles": subtitles,
            "lang": lang,
            "title": title,
            "channel": channel,
        }

        if streaming:
            for chunk in llm_chain.stream(prompt_input):
                yield chunk.content
        else:
            summary = llm_chain.run(prompt_input)
            return summary


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
