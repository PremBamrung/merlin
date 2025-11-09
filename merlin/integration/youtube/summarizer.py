from datetime import datetime
from typing import Generator

from langchain_core.prompts import PromptTemplate

from merlin.llm.azureopenai import llm
from merlin.utils import logger


class VideoSummarizer:
    """Handles video content summarization using LLM."""

    def __init__(self):
        """Initialize summarizer with prompt templates."""
        TEMPLATE_SHORT = """Given the subtitles of a Youtube video, create a short summary that includes:

1. Overview (2 sentences max)
   - First sentence: Summary of what is discussed in the video
   - Second sentence: Must answer the key questions raised in the video - mention specific causes, parties, entities, outcomes, or conclusions discussed (e.g., "The decline is attributed to **policy failures** and voter migration to the **PQ and Liberals**, with recovery unlikely before 2026")
   - Use **markdown bold formatting** to highlight important keywords, themes, parties, entities, or concepts

2. Main Key Points:
   - List up to 10 most important points from the video (this is the highest limit; use fewer points if the content can be adequately summarized with less)
   - Order points by importance, not chronologically
   - Each point should be brief (1-2 lines max) and provide insight, knowledge, or useful information gained from watching the video
   - Focus on actionable insights and key takeaways, not just an enumeration of topics discussed
   - Use **markdown bold formatting** to highlight important keywords, themes, or concepts in each point
   - Avoid verbose explanations; be direct and concise

Examples of good key points:
- "**CAQ projected to lose all seats** due to policy failures and voter migration to PQ and Liberals"
- "**First-past-the-post system** may distort seat allocation, with PQ potentially winning majority with <40% vote"
- "**Legault's leadership** is central to CAQ identity, making leadership change difficult"

Examples of bad key points (too verbose):
- "The CAQ is facing an unprecedented political crisis, with polls suggesting it could lose every seat in the provincial legislature, a stark reversal from its previous landslide victory"
- "Recent by-elections have confirmed the CAQ's decline, with the party suffering major vote losses and finishing far behind rivals, even in former strongholds"

Write the summary in {lang}. Keep it concise and focused on the essentials. Use markdown formatting for emphasis.

Video titled "{title}" from the channel "{channel}"

Subtitles: {subtitles}

# Answer (maintain the numbered structure in the response): """

        TEMPLATE_MEDIUM = """Given the subtitles of a Youtube video, create a medium-length summary that includes:

1. Overview (2-3 sentences)
   - First sentence: Summary of what is discussed in the video
   - Second sentence: Must answer the key questions raised in the video - mention specific causes, parties, entities, outcomes, or conclusions discussed
   - Use **markdown bold formatting** to highlight important keywords, themes, parties, entities, or concepts

2. Main Topics:
   - Extract and list key topics discussed
   - Include timestamps where each topic starts
   - Organize topics hierarchically if possible

3. Key Points:
   - Include 5-8 key points with brief explanations (2-3 lines each)
   - Include relevant timestamps where applicable
   - Each point should provide insight, knowledge, or useful information gained from watching the video
   - Focus on actionable insights and key takeaways, not just an enumeration of topics discussed
   - Use **markdown bold formatting** to highlight important keywords, themes, or concepts in each point
   - Balance conciseness with sufficient context for understanding

4. Important Quotes:
   - Notable statements with timestamps
   - Include speaker attribution if available
   - Use **markdown bold formatting** for emphasis on key quotes

5. Technical Details (if applicable):
   - Specific technical information
   - Definitions or explanations
   - Code examples or technical concepts
   - Use **markdown bold formatting** to highlight technical terms and concepts

Write the summary in {lang}. Focus on clarity and structure. Use markdown formatting for emphasis throughout.

Video titled "{title}" from the channel "{channel}"

Subtitles: {subtitles}

# Answer (maintain the numbered structure in the response): """

        TEMPLATE_LONG = """Given the subtitles of a Youtube video, create a comprehensive, in-depth summary that includes:

1. Overview (3-5 sentences)
   - First sentence: Summary of what is discussed in the video
   - Second sentence: Must answer the key questions raised in the video - mention specific causes, parties, entities, outcomes, or conclusions discussed
   - Additional sentences: Main purpose, theme, context, and overall significance or impact
   - Use **markdown bold formatting** to highlight important keywords, themes, parties, entities, or concepts

2. Main Topics:
   - Extract and list all key topics discussed in detail
   - Include timestamps where each topic starts
   - Organize topics hierarchically with sub-topics
   - Explain the relationship between topics

3. Key Points:
   - Provide 10-15 comprehensive points with supporting context, examples, and explanations (3-5 lines each)
   - Include relevant timestamps where applicable
   - Each point should provide deep insight, knowledge, or useful information gained from watching the video
   - Focus on actionable insights and key takeaways, not just an enumeration of topics discussed
   - Explain the reasoning behind key arguments
   - Use **markdown bold formatting** to highlight important keywords, themes, or concepts in each point

4. Important Quotes:
   - Notable statements with timestamps
   - Include speaker attribution if available
   - Explain the context and significance of each quote
   - Use **markdown bold formatting** for emphasis on key quotes

5. Technical Details (if applicable):
   - Comprehensive technical information
   - Detailed definitions or explanations
   - Code examples or technical concepts with context
   - Step-by-step explanations where relevant
   - Use **markdown bold formatting** to highlight technical terms and concepts

6. Analysis and Insights:
   - Deeper analysis of the content with focus on insights and knowledge gained
   - Connections between different points
   - Implications and applications
   - Critical evaluation where appropriate
   - Use **markdown bold formatting** to highlight key insights

7. Additional Context:
   - Background information relevant to understanding the video
   - Related concepts or prerequisites
   - Further reading or resources mentioned

Write the summary in {lang}. Provide comprehensive detail, context, and analysis. Use markdown formatting for emphasis throughout.

Video titled "{title}" from the channel "{channel}"

Subtitles: {subtitles}

# Answer (maintain the numbered structure in the response): """

        self.templates = {
            "short": PromptTemplate(
                template=TEMPLATE_SHORT,
                input_variables=["subtitles", "lang", "title", "channel"],
            ),
            "medium": PromptTemplate(
                template=TEMPLATE_MEDIUM,
                input_variables=["subtitles", "lang", "title", "channel"],
            ),
            "long": PromptTemplate(
                template=TEMPLATE_LONG,
                input_variables=["subtitles", "lang", "title", "channel"],
            ),
        }

    def extract_topics_and_timestamps(
        self, summary_text: str, summary_length: str = "medium"
    ) -> tuple[dict, dict]:
        """Extract topics and timestamps from the summary text."""
        topics = {}
        timestamps = {}

        # For short summaries, extract from "Main Key Points" section
        if summary_length == "short":
            if "2. Main Key Points:" in summary_text:
                key_points_section = summary_text.split("2. Main Key Points:")[1]
                key_point_lines = [
                    line.strip()
                    for line in key_points_section.split("\n")
                    if line.strip()
                ]

                for line in key_point_lines:
                    if "-" in line or "•" in line:
                        # Handle both "-" and "•" bullet points
                        bullet_char = "-" if "-" in line else "•"
                        point = line.split(bullet_char, 1)[1].strip()
                        # Look for timestamp in the point line
                        if "[" in point and "]" in point:
                            timestamp = point[point.find("[") + 1 : point.find("]")]
                            point = point.split("[")[0].strip()
                            topics[point] = timestamp
                            timestamps[timestamp] = point
        else:
            # For medium and long summaries, extract from "Main Topics" section
            if "2. Main Topics:" in summary_text:
                if "3. Key Points:" in summary_text:
                    topics_section = summary_text.split("2. Main Topics:")[1].split(
                        "3. Key Points:"
                    )[0]
                else:
                    # Fallback if structure is slightly different
                    topics_section = summary_text.split("2. Main Topics:")[1]
                    if "4. Important Quotes:" in topics_section:
                        topics_section = topics_section.split("4. Important Quotes:")[0]

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
            f"Summarization parameters - Language: {lang}, Length: {summary_length}, Streaming: {streaming}"
        )

        # Get the appropriate template based on summary length
        normalized_length = summary_length.lower()
        if normalized_length not in self.templates:
            logger.warning(
                f"Unknown summary length '{summary_length}', defaulting to 'medium'"
            )
            normalized_length = "medium"

        prompt_template = self.templates[normalized_length]
        llm_chain = prompt_template | llm
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
                    # Handle different chunk types from langchain
                    if hasattr(chunk, "content"):
                        content = chunk.content
                    elif isinstance(chunk, str):
                        content = chunk
                    else:
                        # Try to get content from AIMessage or similar
                        content = str(chunk) if chunk else ""

                    if content:
                        yield content
            else:
                # Use invoke() instead of deprecated run()
                response = llm_chain.invoke(prompt_input)
                # Extract content from response
                if hasattr(response, "content"):
                    summary = response.content
                elif isinstance(response, str):
                    summary = response
                else:
                    summary = str(response)

                duration = (datetime.now() - start_time).total_seconds()
                logger.info(f"Summarization completed in {duration:.2f}s")

                # Extract topics and timestamps
                topics, timestamps = self.extract_topics_and_timestamps(
                    summary, normalized_length
                )
                return summary, topics, timestamps
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Summarization failed after {duration:.2f}s: {str(e)}")
            raise
