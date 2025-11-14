"""Tests for YouTube subtitle extraction."""

import pytest

from merlin.integration.youtube.extractors import SubtitleExtractor, VideoExtractor
from merlin.utils import logger


@pytest.fixture
def test_video_url():
    """Default test video URL."""
    return "https://www.youtube.com/watch?v=vuvckBQ1bME"


def test_video_id_extraction(test_video_url):
    """Test video ID extraction from URL."""
    video_id = VideoExtractor.extract_video_id(test_video_url)
    assert video_id is not None
    assert video_id == "vuvckBQ1bME"


def test_subtitle_extraction(test_video_url):
    """Test subtitle extraction for a given YouTube video URL."""
    # Extract video ID
    video_id = VideoExtractor.extract_video_id(test_video_url)
    assert video_id is not None

    # Extract subtitles
    languages = ["en"]  # English
    subtitles = SubtitleExtractor.extract_subtitles(video_id, languages)

    assert subtitles is not None
    assert len(subtitles) > 0

    # Check subtitle structure
    first_subtitle = subtitles[0]
    assert "start" in first_subtitle
    assert "duration" in first_subtitle
    assert "text" in first_subtitle

    # Check that subtitles are in order
    for i in range(len(subtitles) - 1):
        assert subtitles[i]["start"] <= subtitles[i + 1]["start"]


def test_subtitle_text_extraction(test_video_url):
    """Test extracting text from subtitle entries."""
    video_id = VideoExtractor.extract_video_id(test_video_url)
    languages = ["en"]
    subtitles = SubtitleExtractor.extract_subtitles(video_id, languages)

    assert subtitles is not None
    assert len(subtitles) > 0

    # Extract text
    text = SubtitleExtractor.extract_text(subtitles)

    assert text is not None
    assert len(text) > 0
    assert isinstance(text, str)

    # Check that text contains content from subtitles
    word_count = len(text.split())
    assert word_count > 0


def test_subtitle_statistics(test_video_url):
    """Test subtitle statistics calculation."""
    video_id = VideoExtractor.extract_video_id(test_video_url)
    languages = ["en"]
    subtitles = SubtitleExtractor.extract_subtitles(video_id, languages)

    assert subtitles is not None
    assert len(subtitles) > 0

    # Calculate total duration
    if subtitles:
        total_duration = (
            subtitles[-1]["start"] + subtitles[-1]["duration"] if subtitles else 0
        )
        assert total_duration > 0

        # Check first and last entry times
        assert subtitles[0]["start"] >= 0
        assert subtitles[-1]["start"] >= subtitles[0]["start"]


@pytest.mark.parametrize(
    "video_url,expected_id",
    [
        ("https://www.youtube.com/watch?v=vuvckBQ1bME", "vuvckBQ1bME"),
        ("https://youtu.be/vuvckBQ1bME", "vuvckBQ1bME"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_video_id_extraction_various_formats(video_url, expected_id):
    """Test video ID extraction from various URL formats."""
    video_id = VideoExtractor.extract_video_id(video_url)
    assert video_id == expected_id
