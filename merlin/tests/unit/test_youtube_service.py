from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from merlin.youtube.service import VideoResult, YouTubeService


@pytest.fixture
def youtube_service():
    """Create a YouTubeService instance with mocked dependencies."""
    service = YouTubeService()
    service.extractor = MagicMock()
    service.llm_service = MagicMock()
    return service


@pytest.mark.asyncio
async def test_process_video_success(youtube_service):
    """Test successful video processing."""
    # Mock data
    test_url = "https://www.youtube.com/watch?v=test_id"
    test_video_id = "test_id"
    test_metadata = {
        "title": "Test Video",
        "channel": "Test Channel",
        "date": datetime.now(),
        "views": 1000,
        "duration": "10:00",
        "subscribers": "1M",
        "videos_count": "100",
    }
    test_transcript = "This is a test transcript"
    test_summary_result = {
        "summary": "Test summary",
        "topics": {"Topic 1": "0:00", "Topic 2": "5:00"},
        "timestamps": {"Moment 1": "2:30", "Moment 2": "7:30"},
    }

    # Configure mocks
    youtube_service.extractor.extract_video_id.return_value = test_video_id
    youtube_service.extractor.get_video_metadata = AsyncMock(return_value=test_metadata)
    youtube_service.extractor.get_transcript = AsyncMock(return_value=test_transcript)
    youtube_service.llm_service.process_text = AsyncMock(
        return_value=test_summary_result
    )

    # Call the method
    result = await youtube_service.process_video(
        url=test_url, language="english", summary_length="short"
    )

    # Verify the result
    assert isinstance(result, VideoResult)
    assert result.video_id == test_video_id
    assert result.title == test_metadata["title"]
    assert result.channel == test_metadata["channel"]
    assert result.summary == test_summary_result["summary"]
    assert result.topics == test_summary_result["topics"]
    assert result.timestamps == test_summary_result["timestamps"]

    # Verify mock calls
    youtube_service.extractor.extract_video_id.assert_called_once_with(test_url)
    youtube_service.extractor.get_video_metadata.assert_called_once_with(test_video_id)
    youtube_service.extractor.get_transcript.assert_called_once_with(
        test_video_id, "english"
    )
    youtube_service.llm_service.process_text.assert_called_once_with(
        text=test_transcript,
        task="summarize",
        options={
            "language": "english",
            "length": "short",
            "extract_topics": True,
            "extract_timestamps": True,
        },
    )


@pytest.mark.asyncio
async def test_process_video_invalid_url(youtube_service):
    """Test processing with invalid URL."""
    youtube_service.extractor.extract_video_id.return_value = None

    with pytest.raises(ValueError, match="Invalid YouTube URL"):
        await youtube_service.process_video("invalid_url")


@pytest.mark.asyncio
async def test_process_video_no_transcript(youtube_service):
    """Test processing when transcript is not available."""
    youtube_service.extractor.extract_video_id.return_value = "test_id"
    youtube_service.extractor.get_video_metadata = AsyncMock(return_value={})
    youtube_service.extractor.get_transcript = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="Could not fetch video transcript"):
        await youtube_service.process_video("https://www.youtube.com/watch?v=test_id")


@pytest.mark.asyncio
async def test_get_video_metadata(youtube_service):
    """Test getting video metadata."""
    test_metadata = {"title": "Test Video"}
    youtube_service.extractor.get_video_metadata = AsyncMock(return_value=test_metadata)

    result = await youtube_service.get_video_metadata("test_id")
    assert result == test_metadata
    youtube_service.extractor.get_video_metadata.assert_called_once_with("test_id")


@pytest.mark.asyncio
async def test_get_transcript(youtube_service):
    """Test getting video transcript."""
    test_transcript = "Test transcript"
    youtube_service.extractor.get_transcript = AsyncMock(return_value=test_transcript)

    result = await youtube_service.get_transcript("test_id", "english")
    assert result == test_transcript
    youtube_service.extractor.get_transcript.assert_called_once_with(
        "test_id", "english"
    )
