import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from merlin.llm.service import LLMProvider, LLMService


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI API response."""
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content="""Here's a summary of the text:

                This is a test summary.

                Main Topics and Timestamps:
                Introduction: 0:00
                Key Point 1: 5:00

                Important Moments:
                Highlight 1: 2:30
                Highlight 2: 7:30"""
            )
        )
    ]
    return mock_response


@pytest.fixture
def llm_service():
    """Create LLMService instance with mocked client."""
    with patch.dict(os.environ, {"AZURE_OPENAI_KEY": "test_key"}):
        service = LLMService()
        service.client = AsyncMock()
        return service


@pytest.mark.asyncio
async def test_process_text_summarize(llm_service, mock_openai_response):
    """Test text summarization with topic and timestamp extraction."""
    # Configure mock
    llm_service.client.chat.completions.create = AsyncMock(
        return_value=mock_openai_response
    )

    # Test data
    test_text = "This is a test text to summarize."
    options = {
        "language": "english",
        "length": "short",
        "extract_topics": True,
        "extract_timestamps": True,
    }

    # Call the method
    result = await llm_service.process_text(
        text=test_text, task="summarize", options=options
    )

    # Verify the result
    assert "summary" in result
    assert result["summary"].strip() == "This is a test summary."
    assert "topics" in result
    assert result["topics"] == {"Introduction": "0:00", "Key Point 1": "5:00"}
    assert "timestamps" in result
    assert result["timestamps"] == {"Highlight 1": "2:30", "Highlight 2": "7:30"}

    # Verify the prompt
    llm_service.client.chat.completions.create.assert_called_once()
    call_args = llm_service.client.chat.completions.create.call_args
    assert "messages" in call_args[1]
    messages = call_args[1]["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert test_text in messages[1]["content"]
    assert "concise" in messages[1]["content"]  # short -> concise in prompt
    assert "english" in messages[1]["content"]


@pytest.mark.asyncio
async def test_process_text_error(llm_service):
    """Test error handling in text processing."""
    # Configure mock to raise an exception
    llm_service.client.chat.completions.create = AsyncMock(
        side_effect=Exception("API Error")
    )

    # Test error handling
    with pytest.raises(Exception, match="Error processing text with LLM: API Error"):
        await llm_service.process_text("test text")


def test_get_default_provider():
    """Test provider selection based on environment variables."""
    # Test Azure OpenAI selection
    with patch.dict(os.environ, {"AZURE_OPENAI_KEY": "test_key"}):
        service = LLMService()
        assert service.provider == LLMProvider.AZURE_OPENAI

    # Test OpenRouter fallback
    with patch.dict(os.environ, {"AZURE_OPENAI_KEY": ""}):
        service = LLMService()
        assert service.provider == LLMProvider.OPENROUTER


def test_get_model():
    """Test model selection based on provider and task."""
    # Test Azure OpenAI model
    with patch.dict(
        os.environ,
        {"AZURE_OPENAI_KEY": "test_key", "AZURE_OPENAI_DEPLOYMENT": "test-deployment"},
    ):
        service = LLMService()
        assert service.provider == LLMProvider.AZURE_OPENAI
        assert service._get_model("summarize") == "test-deployment"

    # Test OpenRouter model selection
    with patch.dict(os.environ, {"AZURE_OPENAI_KEY": ""}):
        service = LLMService()
        assert service.provider == LLMProvider.OPENROUTER
        assert service._get_model("summarize") == "anthropic/claude-3-opus"
        assert service._get_model("other") == "anthropic/claude-3-sonnet"
