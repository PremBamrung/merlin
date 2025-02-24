from datetime import datetime
from typing import Generator

from langchain_core.prompts import PromptTemplate

from merlin.llm.openrouter import llm
from merlin.utils import logger


class VideoSummarizer:
    """Handles video content summarization using LLM."""

    def __init__(self):
        """Initialize summarizer with prompt templates."""
        TEMPLATE = """Given the subtitles of a Youtube video, create a {length} summary that includes:

1. Overview (2-3 sentences)
2. Main Topics:
   - Extract and list key topics discussed
   - Include timestamps where each topic starts
   - Organize topics hierarchically if possible

3. Key Points:
   - Bullet points of main arguments/ideas
   - Include relevant timestamps
   - {length_specific_instructions}

4. Important Quotes:
   - Notable statements with timestamps
   - Include speaker attribution if available

5. Technical Details (if applicable):
   - Specific technical information
   - Definitions or explanations
   - Code examples or technical concepts

Write the summary in {lang}. Focus on clarity and structure.

Video titled "{title}" from the channel "{channel}"

Subtitles: {subtitles}

# Answer (maintain the numbered structure in the response): """

        length_instructions = {
            "short": "Focus on 3-5 most crucial points",
            "medium": "Include 5-8 key points with brief explanations",
            "long": "Provide 8-12 detailed points with supporting context",
        }

        self.prompt_template = PromptTemplate(
            template=TEMPLATE,
            input_variables=[
                "subtitles",
                "lang",
                "title",
                "channel",
                "length",
                "length_specific_instructions",
            ],
        )
        self.length_instructions = length_instructions

    def extract_topics_and_timestamps(self, summary_text: str) -> tuple[dict, dict]:
        """Extract topics and timestamps from the summary text."""
        topics = {}
        timestamps = {}

        # Extract topics from the "Main Topics" section
        topics_section = summary_text.split("2. Main Topics:")[1].split(
            "3. Key Points:"
        )[0]
        topic_lines = [
            line.strip() for line in topics_section.split("\n") if line.strip()
        ]

        for line in topic_lines:
            if "-" in line:
                topic = line.split("-")[1].strip()
                # Look for timestamp in the topic line
                if "[" in topic and "]" in topic:
                    timestamp = topic[topic.find("[") + 1 : topic.find("]")]
                    topic = topic.split("[")[0].strip()
                    topics[topic] = timestamp
                    timestamps[timestamp] = topic

        return topics, timestamps

    def summarize(
        self,
        subtitles: str,
        title: str,
        channel: str,
        lang: str = "english",
        summary_length: str = "medium",
        streaming: bool = False,
    ) -> Generator[str, None, None] | tuple[str, dict, dict]:
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
                summary_text = ""
                for chunk in llm_chain.stream(
                    {
                        **prompt_input,
                        "length": summary_length,
                        "length_specific_instructions": self.length_instructions[
                            summary_length
                        ],
                    }
                ):
                    summary_text += chunk.content
                    yield chunk.content

                # Extract topics and timestamps after streaming
                topics, timestamps = self.extract_topics_and_timestamps(summary_text)
                return summary_text, topics, timestamps
            else:
                summary = llm_chain.run(
                    {
                        **prompt_input,
                        "length": summary_length,
                        "length_specific_instructions": self.length_instructions[
                            summary_length
                        ],
                    }
                )
                duration = (datetime.now() - start_time).total_seconds()
                logger.info(f"Summarization completed in {duration:.2f}s")

                # Extract topics and timestamps
                topics, timestamps = self.extract_topics_and_timestamps(summary)
                return summary, topics, timestamps
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Summarization failed after {duration:.2f}s: {str(e)}")
            raise
