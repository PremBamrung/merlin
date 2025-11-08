#!/usr/bin/env python3
"""
Test script for YouTube subtitle extraction.
Tests subtitle extraction on a specific video with English subtitles.
"""

import sys

from merlin.integration.youtube.extractors import SubtitleExtractor, VideoExtractor
from merlin.utils import logger


def test_subtitle_extraction(video_url: str):
    """Test subtitle extraction for a given YouTube video URL."""
    print("=" * 80)
    print("YouTube Subtitle Extraction Test")
    print("=" * 80)
    print(f"\nVideo URL: {video_url}\n")

    # Extract video ID
    video_id = VideoExtractor.extract_video_id(video_url)
    if not video_id:
        print("❌ Failed to extract video ID from URL")
        return False

    print(f"✅ Video ID extracted: {video_id}\n")

    # Extract subtitles
    print("Extracting subtitles...")
    print("-" * 80)

    languages = ["en"]  # English
    subtitles = SubtitleExtractor.extract_subtitles(video_id, languages)

    if not subtitles:
        print("❌ Failed to extract subtitles")
        return False

    print(f"\n✅ Successfully extracted {len(subtitles)} subtitle entries\n")

    # Display some statistics
    total_duration = (
        subtitles[-1]["start"] + subtitles[-1]["duration"] if subtitles else 0
    )
    print(f"Subtitle Statistics:")
    print(f"  - Total entries: {len(subtitles)}")
    print(
        f"  - Video duration: {total_duration:.2f} seconds ({total_duration/60:.2f} minutes)"
    )
    print(f"  - First entry time: {subtitles[0]['start']:.2f}s")
    print(f"  - Last entry time: {subtitles[-1]['start']:.2f}s")

    # Extract and display text
    text = SubtitleExtractor.extract_text(subtitles)
    word_count = len(text.split())
    char_count = len(text)

    print(f"\nText Statistics:")
    print(f"  - Total words: {word_count:,}")
    print(f"  - Total characters: {char_count:,}")

    # Display first few subtitle entries
    print(f"\nFirst 10 subtitle entries:")
    print("-" * 80)
    for i, sub in enumerate(subtitles[:10], 1):
        start_time = sub["start"]
        minutes = int(start_time // 60)
        seconds = int(start_time % 60)
        print(f"{i:2d}. [{minutes:02d}:{seconds:02d}] {sub['text']}")

    if len(subtitles) > 10:
        print(f"\n... and {len(subtitles) - 10} more entries")

    # Display last few subtitle entries
    if len(subtitles) > 10:
        print(f"\nLast 5 subtitle entries:")
        print("-" * 80)
        for i, sub in enumerate(subtitles[-5:], len(subtitles) - 4):
            start_time = sub["start"]
            minutes = int(start_time // 60)
            seconds = int(start_time % 60)
            print(f"{i:2d}. [{minutes:02d}:{seconds:02d}] {sub['text']}")

    # Display a sample of the full text (first 500 characters)
    print(f"\nSample text (first 500 characters):")
    print("-" * 80)
    print(text[:500])
    if len(text) > 500:
        print("...")

    print("\n" + "=" * 80)
    print("✅ Test completed successfully!")
    print("=" * 80)

    return True


if __name__ == "__main__":
    # Test video URL
    test_url = "https://www.youtube.com/watch?v=vuvckBQ1bME"

    if len(sys.argv) > 1:
        test_url = sys.argv[1]

    try:
        success = test_subtitle_extraction(test_url)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error during test: {str(e)}")
        logger.exception("Test failed with exception")
        sys.exit(1)
