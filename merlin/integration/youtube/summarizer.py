from datetime import datetime
from typing import Generator

from langchain_core.prompts import PromptTemplate

from merlin.llm.openrouter import llm
from merlin.utils import logger


class VideoSummarizer:
    """Handles video content summarization using LLM."""

    def __init__(self):
        """Initialize summarizer with prompt template."""
        TEMPLATE = """Given the subtitles of a Youtube video,
        Write a short summary in bullet points, extracting the main key information. Format the summary using clean and concise bullet points, highlighting the main ideas. Write the summary in {lang}
        # Video  titled "{title}" from the channel "{channel}"

        # The subtitles :{subtitles}

        # Answer: """

        self.prompt_template = PromptTemplate(
            template=TEMPLATE, input_variables=["subtitles", "lang", "title", "channel"]
        )

    def summarize(
        self,
        subtitles: str,
        title: str,
        channel: str,
        lang: str = "english",
        streaming: bool = False,
    ) -> Generator[str, None, None] | str:
        """Generate a summary of the video content.

        Args:
            subtitles: The video subtitles text
            title: The video title
            channel: The channel name
            lang: Target language for the summary
            streaming: Whether to stream the response

        Returns:
            Either a generator yielding summary chunks (if streaming=True)
            or the complete summary text
        """
        start_time = datetime.now()
        logger.info(f"Starting summarization for video: {title}")
        logger.debug(
            f"Summarization parameters - Language: {lang}, Streaming: {streaming}"
        )

        llm_chain = self.prompt_template | llm
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
                duration = (datetime.now() - start_time).total_seconds()
                logger.info(f"Summarization completed in {duration:.2f}s")
                return summary
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Summarization failed after {duration:.2f}s: {str(e)}")
            raise
