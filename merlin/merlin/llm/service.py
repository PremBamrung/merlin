import os
from enum import Enum
from typing import Dict, Optional, Union

import httpx
from openai import AsyncAzureOpenAI, AsyncOpenAI


class LLMProvider(Enum):
    AZURE_OPENAI = "azure_openai"
    OPENROUTER = "openrouter"


class LLMService:
    def __init__(self, provider: str = None):
        self.provider = (
            LLMProvider(provider) if provider else self._get_default_provider()
        )
        self.client = self._initialize_client()

    def _get_default_provider(self) -> LLMProvider:
        """Determine default provider based on available credentials."""
        # if os.getenv("AZURE_OPENAI_KEY"):
        #     return LLMProvider.AZURE_OPENAI
        return LLMProvider.OPENROUTER

    def _initialize_client(self) -> Union[AsyncAzureOpenAI, AsyncOpenAI]:
        """Initialize the appropriate LLM client."""
        if self.provider == LLMProvider.AZURE_OPENAI:
            return AsyncAzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            )
        else:
            return AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.getenv("OPENROUTER_API_KEY"),
            )

    def _get_model(self, task: str) -> str:
        """Get appropriate model based on task and provider."""
        if self.provider == LLMProvider.AZURE_OPENAI:
            return os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")

        # OpenRouter model selection
        if task == "summarize":
            return "google/gemini-2.0-flash-001"
        return "google/gemini-2.0-flash-001"

    def _create_prompt(self, text: str, task: str, options: Dict) -> str:
        """Create appropriate prompt based on task."""
        if task == "summarize":
            length_map = {
                "short": "concise",
                "medium": "moderate-length",
                "long": "detailed",
            }
            length = length_map.get(options.get("length", "short"), "concise")
            language = options.get("language", "english")

            prompt = f"""Please provide a {length} summary of the following text in {language}.

            If topics extraction is requested, identify the main topics and their timestamps.
            If timestamps extraction is requested, identify key moments in the content.

            Text to summarize:
            {text}
            """

            if options.get("extract_topics"):
                prompt += "\n\nPlease also extract main topics and their timestamps."

            if options.get("extract_timestamps"):
                prompt += (
                    "\n\nPlease also identify important moments and their timestamps."
                )

            return prompt

        return text

    async def process_text(
        self, text: str, task: str = "summarize", options: Optional[Dict] = None
    ) -> Dict:
        """Process text using the configured LLM provider."""
        options = options or {}
        model = self._get_model(task)
        prompt = self._create_prompt(text, task, options)

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant specializing in text analysis and summarization.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )

            result = response.choices[0].message.content

            # Parse the response based on task
            if task == "summarize":
                summary_parts = result.split("\n\n")
                response_dict = {"summary": summary_parts[0]}

                if options.get("extract_topics") and len(summary_parts) > 1:
                    response_dict["topics"] = self._parse_topics(summary_parts[1])

                if options.get("extract_timestamps") and len(summary_parts) > 2:
                    response_dict["timestamps"] = self._parse_timestamps(
                        summary_parts[2]
                    )

                return response_dict

            return {"result": result}

        except Exception as e:
            raise Exception(f"Error processing text with LLM: {str(e)}")

    def _parse_topics(self, topics_text: str) -> Dict:
        """Parse topics and their timestamps from LLM response."""
        topics = {}
        try:
            lines = topics_text.split("\n")
            for line in lines:
                if ":" in line:
                    topic, timestamp = line.split(":", 1)
                    topics[topic.strip()] = timestamp.strip()
        except Exception:
            pass
        return topics

    def _parse_timestamps(self, timestamps_text: str) -> Dict:
        """Parse important moments and their timestamps from LLM response."""
        timestamps = {}
        try:
            lines = timestamps_text.split("\n")
            for line in lines:
                if ":" in line:
                    moment, timestamp = line.split(":", 1)
                    timestamps[moment.strip()] = timestamp.strip()
        except Exception:
            pass
        return timestamps
