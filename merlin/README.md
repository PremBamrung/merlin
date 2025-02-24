# Merlin Library

A Python library for fetching and processing YouTube videos with LLM integration.

## Features

- YouTube video data extraction
- Transcript fetching and processing
- LLM-powered summarization
- Support for multiple LLM providers (Azure OpenAI, OpenRouter)
- Multi-language support

## Installation

```bash
pip install -e .
```

## Usage

```python
from merlin.youtube import YouTubeService

# Initialize the service
youtube_service = YouTubeService()

# Process a video
result = await youtube_service.process_video(
    url="https://www.youtube.com/watch?v=your_video_id",
    language="english",
    summary_length="short"
)

# Access the results
print(f"Title: {result.title}")
print(f"Summary: {result.summary}")
print(f"Topics: {result.topics}")
```

## Environment Variables

The library requires the following environment variables:

```bash
# For Azure OpenAI
AZURE_OPENAI_KEY=your_key
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_DEPLOYMENT=your_deployment_name

# For OpenRouter
OPENROUTER_API_KEY=your_key
```

## Development

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run tests: `pytest`

## License

MIT License
