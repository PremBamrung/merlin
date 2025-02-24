from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from youtube_transcript_api import Transcript, TranscriptList

from merlin.youtube.extractor import VideoExtractor


@pytest.fixture
def video_extractor():
    """Create VideoExtractor instance."""
    return VideoExtractor()


def test_extract_video_id_standard_url(video_extractor):
    """Test extracting video ID from standard YouTube URL."""
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    video_id = video_extractor.extract_video_id(url)
    assert video_id == "dQw4w9WgXcQ"


def test_extract_video_id_short_url(video_extractor):
    """Test extracting video ID from youtu.be URL."""
    url = "https://youtu.be/dQw4w9WgXcQ"
    video_id = video_extractor.extract_video_id(url)
    assert video_id == "dQw4w9WgXcQ"


def test_extract_video_id_embed_url(video_extractor):
    """Test extracting video ID from embed URL."""
    url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
    video_id = video_extractor.extract_video_id(url)
    assert video_id == "dQw4w9WgXcQ"


def test_extract_video_id_invalid_url(video_extractor):
    """Test extracting video ID from invalid URL."""
    url = "https://example.com"
    video_id = video_extractor.extract_video_id(url)
    assert video_id is None


@pytest.mark.asyncio
async def test_get_video_metadata_success(video_extractor):
    """Test successful video metadata extraction."""
    # Mock response
    mock_response = MagicMock()
    mock_response.text = """
    <meta property="og:title" content="Test Video">
    <meta property="og:channelName" content="Test Channel">
    """

    # Mock httpx client
    with patch.object(
        video_extractor.client, "get", AsyncMock(return_value=mock_response)
    ):
        metadata = await video_extractor.get_video_metadata("test_id")

        assert metadata["title"] == "Test Video"
        assert metadata["channel"] == "Test Channel"
        assert isinstance(metadata["date"], datetime)
        assert "views" in metadata
        assert "duration" in metadata
        assert "subscribers" in metadata
        assert "videos_count" in metadata


@pytest.mark.asyncio
async def test_get_video_metadata_error(video_extractor):
    """Test error handling in metadata extraction."""
    with patch.object(
        video_extractor.client, "get", AsyncMock(side_effect=Exception("Network error"))
    ):
        with pytest.raises(ValueError, match="Failed to fetch video metadata"):
            await video_extractor.get_video_metadata("test_id")


@pytest.mark.asyncio
async def test_get_transcript_success(video_extractor):
    """Test successful transcript fetching."""
    # Mock transcript data
    mock_transcript = [
        {"text": "First part", "start": 0.0, "duration": 2.0},
        {"text": "Second part", "start": 2.0, "duration": 2.0},
    ]

    # Mock TranscriptList
    mock_transcript_list = MagicMock(spec=TranscriptList)
    mock_transcript_obj = MagicMock(spec=Transcript)
    mock_transcript_obj.fetch.return_value = mock_transcript
    mock_transcript_list.find_transcript.return_value = mock_transcript_obj

    with patch(
        "youtube_transcript_api.YouTubeTranscriptApi.list_transcripts",
        return_value=mock_transcript_list,
    ):
        transcript = await video_extractor.get_transcript("test_id", "english")

        assert transcript == "First part Second part"
        mock_transcript_list.find_transcript.assert_called_once_with(["english"])


@pytest.mark.asyncio
async def test_get_transcript_language_fallback(video_extractor):
    """Test transcript language fallback behavior."""
    mock_transcript = [{"text": "Content", "start": 0.0, "duration": 2.0}]
    mock_transcript_list = MagicMock(spec=TranscriptList)
    mock_transcript_obj = MagicMock(spec=Transcript)
    mock_transcript_obj.fetch.return_value = mock_transcript

    # Simulate primary language not found
    mock_transcript_list.find_transcript.side_effect = [
        Exception("Language not found"),  # First call fails
        mock_transcript_obj,  # Second call succeeds (fallback to English)
    ]

    with patch(
        "youtube_transcript_api.YouTubeTranscriptApi.list_transcripts",
        return_value=mock_transcript_list,
    ):
        transcript = await video_extractor.get_transcript("test_id", "nonexistent")

        assert transcript == "Content"
        assert mock_transcript_list.find_transcript.call_count == 2
        mock_transcript_list.find_transcript.assert_called_with(["en"])


@pytest.mark.asyncio
async def test_get_transcript_not_available(video_extractor):
    """Test handling when no transcript is available."""
    with patch(
        "youtube_transcript_api.YouTubeTranscriptApi.list_transcripts",
        side_effect=Exception("No transcript available"),
    ):
        transcript = await video_extractor.get_transcript("test_id")
        assert transcript is None


def test_extract_meta_content(video_extractor):
    """Test meta content extraction from HTML."""
    html = '<meta property="og:title" content="Test Title">'
    content = video_extractor._extract_meta_content(html, "title")
    assert content == "Test Title"

    # Test with missing meta tag
    content = video_extractor._extract_meta_content(html, "nonexistent")
    assert content is None
