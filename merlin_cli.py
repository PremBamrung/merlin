#!/usr/bin/env python3
"""
Merlin CLI - Lightweight command-line interface for content summarization.
No database connection required - just quick terminal summaries.

Usage:
    python merlin_cli.py <source> <url_or_path> [options]

Sources:
    youtube    - Summarize YouTube videos
    (more sources coming soon: reddit, article, pdf, etc.)
"""

import argparse
from pathlib import Path
import sys

from dotenv import load_dotenv

from merlin.utils import logger


def format_content_output(
    content_info: dict,
    summary: str,
    topics: dict = None,
    timestamps: dict = None,
    show_full: bool = False,
) -> str:
    """Format content summary output for CLI display."""
    if topics is None:
        topics = {}
    if timestamps is None:
        timestamps = {}

    output = []
    output.append("=" * 80)
    output.append("📄 CONTENT INFORMATION")
    output.append("=" * 80)

    # Display content-specific metadata
    for key, value in content_info.items():
        if value and key != "raw_content":
            # Format key names nicely
            display_key = key.replace("_", " ").title()
            output.append(f"{display_key}: {value}")

    output.append("")

    if summary:
        output.append("=" * 80)
        output.append("📝 SUMMARY")
        output.append("=" * 80)
        output.append(summary)
        output.append("")

    if topics and show_full:
        output.append("=" * 80)
        output.append("🔑 KEY TOPICS")
        output.append("=" * 80)
        for topic, timestamp in topics.items():
            output.append(f"  • {topic} [{timestamp}]")
        output.append("")

    if timestamps and show_full:
        output.append("=" * 80)
        output.append("⏱️  TIMESTAMPS")
        output.append("=" * 80)
        for timestamp, description in timestamps.items():
            output.append(f"  [{timestamp}] {description}")
        output.append("")

    output.append("=" * 80)
    return "\n".join(output)


def process_youtube(
    url: str,
    lang: str = "english",
    summary_length: str = "medium",
    show_full: bool = False,
) -> int:
    """Process a YouTube video and display the summary."""
    try:
        from merlin.integration.youtube.audio_transcriber import AudioTranscriber
        from merlin.integration.youtube.extractors import (
            SubtitleExtractor,
            VideoExtractor,
        )
        from merlin.integration.youtube.summarizer import VideoSummarizer

        print("🔄 Extracting video information...", file=sys.stderr)

        # Extract video ID and info
        video_extractor = VideoExtractor()
        video_id = video_extractor.extract_video_id(url)
        if not video_id:
            print("❌ Error: Invalid YouTube URL", file=sys.stderr)
            return 1

        video_info = video_extractor.extract_video_info(url)
        if not video_info:
            print("❌ Error: Failed to extract video information", file=sys.stderr)
            return 1
        video_info["video_id"] = video_id

        # Extract subtitles
        print("🔄 Extracting subtitles...", file=sys.stderr)
        subtitle_extractor = SubtitleExtractor()
        subtitle_result = subtitle_extractor.extract_subtitles(
            video_id, ["en", "fr", "de"]
        )

        if not subtitle_result:
            print(
                "⚠️  No subtitles found, attempting audio transcription...",
                file=sys.stderr,
            )
            # Fallback: download audio and transcribe
            success, fallback_subtitles, error_msg = AudioTranscriber.transcribe_video(
                url
            )
            if success and fallback_subtitles:
                print(
                    f"✅ Transcribed audio ({len(fallback_subtitles)} segments)",
                    file=sys.stderr,
                )
                # For audio transcription, create dict format
                subtitle_result = {
                    "subtitles": fallback_subtitles,
                    "language_code": "en",  # Default for audio transcription
                }
            else:
                print("❌ Error: Failed to extract subtitles", file=sys.stderr)
                if error_msg:
                    if "GROQ_API_KEY" in error_msg:
                        print(
                            "💡 Tip: Audio transcription requires GROQ_API_KEY in your .env file",
                            file=sys.stderr,
                        )
                        print(
                            "   Set GROQ_API_KEY=your_key in merlin/.env to enable audio transcription",
                            file=sys.stderr,
                        )
                    else:
                        print(f"   Details: {error_msg}", file=sys.stderr)
                else:
                    print(
                        "   This video may not have subtitles available.",
                        file=sys.stderr,
                    )
                return 1

        # Extract subtitles list from result
        subtitles = subtitle_result["subtitles"]

        # Convert subtitles to text
        print("🔄 Processing transcript...", file=sys.stderr)
        text = subtitle_extractor.extract_text(subtitles)
        if not text:
            print("❌ Error: Failed to extract text from subtitles", file=sys.stderr)
            return 1

        # Generate summary
        print("🔄 Generating summary...", file=sys.stderr)
        summarizer = VideoSummarizer()
        summary, topics, timestamps = summarizer.summarize(
            subtitles=text,
            title=video_info["title"],
            channel=video_info["channel"],
            lang=lang,
            summary_length=summary_length,
            streaming=False,
        )

        # Format content info for generic display
        content_info = {
            "title": video_info.get("title", ""),
            "channel": video_info.get("channel", ""),
            "duration": video_info.get("duration", ""),
            "views": video_info.get("views", ""),
            "published": video_info.get("date", ""),
            "video_id": video_info.get("video_id", ""),
        }

        print("✅ Summary generated successfully", file=sys.stderr)
        print("")
        print(
            format_content_output(
                content_info, summary, topics, timestamps, show_full=show_full
            )
        )
        return 0

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        logger.error(f"Error processing YouTube video: {str(e)}")
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        return 1


def process_reddit(
    url: str,
    lang: str = "english",
    summary_length: str = "medium",
    show_full: bool = False,
) -> int:
    """Process a Reddit post/thread and display the summary."""
    print("❌ Error: Reddit integration not yet implemented", file=sys.stderr)
    print("💡 This feature is coming soon!", file=sys.stderr)
    return 1


def process_article(
    url: str,
    lang: str = "english",
    summary_length: str = "medium",
    show_full: bool = False,
) -> int:
    """Process a web article and display the summary."""
    print("❌ Error: Article integration not yet implemented", file=sys.stderr)
    print("💡 This feature is coming soon!", file=sys.stderr)
    return 1


def process_pdf(
    file_path: str,
    lang: str = "english",
    summary_length: str = "medium",
    show_full: bool = False,
) -> int:
    """Process a PDF document and display the summary."""
    print("❌ Error: PDF integration not yet implemented", file=sys.stderr)
    print("💡 This feature is coming soon!", file=sys.stderr)
    return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Merlin CLI - Lightweight content summarization tool (no database)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Summarize a YouTube video
  python merlin_cli.py youtube https://www.youtube.com/watch?v=VIDEO_ID

  # Summarize with custom options
  python merlin_cli.py youtube https://www.youtube.com/watch?v=VIDEO_ID --lang french --length long

  # Show full output with topics and timestamps
  python merlin_cli.py youtube https://www.youtube.com/watch?v=VIDEO_ID --full

Supported sources:
  youtube    - YouTube videos (implemented)
  reddit     - Reddit posts/threads (coming soon)
  article    - Web articles (coming soon)
  pdf        - PDF documents (coming soon)
        """,
    )

    # Subcommands
    subparsers = parser.add_subparsers(
        dest="source", help="Content source type", required=True
    )

    # YouTube subcommand
    youtube_parser = subparsers.add_parser("youtube", help="Summarize YouTube videos")
    youtube_parser.add_argument("url", help="YouTube video URL")
    youtube_parser.add_argument(
        "--lang",
        default="english",
        choices=["english", "french", "german"],
        help="Language for the summary (default: english)",
    )
    youtube_parser.add_argument(
        "--length",
        "--summary-length",
        dest="summary_length",
        default="medium",
        choices=["short", "medium", "long"],
        help="Summary length: short, medium, or long (default: medium)",
    )
    youtube_parser.add_argument(
        "--full",
        action="store_true",
        help="Show full output including topics and timestamps",
    )

    # Reddit subcommand (placeholder)
    reddit_parser = subparsers.add_parser(
        "reddit", help="Summarize Reddit posts/threads (coming soon)"
    )
    reddit_parser.add_argument("url", help="Reddit post/thread URL")
    reddit_parser.add_argument(
        "--lang",
        default="english",
        choices=["english", "french", "german"],
        help="Language for the summary (default: english)",
    )
    reddit_parser.add_argument(
        "--length",
        "--summary-length",
        dest="summary_length",
        default="medium",
        choices=["short", "medium", "long"],
        help="Summary length: short, medium, or long (default: medium)",
    )
    reddit_parser.add_argument(
        "--full",
        action="store_true",
        help="Show full output including topics and timestamps",
    )

    # Article subcommand (placeholder)
    article_parser = subparsers.add_parser(
        "article", help="Summarize web articles (coming soon)"
    )
    article_parser.add_argument("url", help="Article URL")
    article_parser.add_argument(
        "--lang",
        default="english",
        choices=["english", "french", "german"],
        help="Language for the summary (default: english)",
    )
    article_parser.add_argument(
        "--length",
        "--summary-length",
        dest="summary_length",
        default="medium",
        choices=["short", "medium", "long"],
        help="Summary length: short, medium, or long (default: medium)",
    )
    article_parser.add_argument(
        "--full",
        action="store_true",
        help="Show full output including topics and timestamps",
    )

    # PDF subcommand (placeholder)
    pdf_parser = subparsers.add_parser(
        "pdf", help="Summarize PDF documents (coming soon)"
    )
    pdf_parser.add_argument("file_path", help="Path to PDF file")
    pdf_parser.add_argument(
        "--lang",
        default="english",
        choices=["english", "french", "german"],
        help="Language for the summary (default: english)",
    )
    pdf_parser.add_argument(
        "--length",
        "--summary-length",
        dest="summary_length",
        default="medium",
        choices=["short", "medium", "long"],
        help="Summary length: short, medium, or long (default: medium)",
    )
    pdf_parser.add_argument(
        "--full",
        action="store_true",
        help="Show full output including topics and timestamps",
    )

    args = parser.parse_args()

    # Load environment variables from project root first
    project_root = Path(__file__).parent
    root_env_path = project_root / ".env"
    merlin_env_path = project_root / "merlin" / ".env"

    # Try root .env first, then merlin/.env for backwards compatibility
    if root_env_path.exists():
        load_dotenv(root_env_path)
    if merlin_env_path.exists():
        load_dotenv(merlin_env_path, override=False)

    # Fallback to default behavior
    if not root_env_path.exists() and not merlin_env_path.exists():
        load_dotenv()

    # Route to appropriate processor
    if args.source == "youtube":
        return process_youtube(
            url=args.url,
            lang=args.lang,
            summary_length=args.summary_length,
            show_full=args.full,
        )
    elif args.source == "reddit":
        return process_reddit(
            url=args.url,
            lang=args.lang,
            summary_length=args.summary_length,
            show_full=args.full,
        )
    elif args.source == "article":
        return process_article(
            url=args.url,
            lang=args.lang,
            summary_length=args.summary_length,
            show_full=args.full,
        )
    elif args.source == "pdf":
        return process_pdf(
            file_path=args.file_path,
            lang=args.lang,
            summary_length=args.summary_length,
            show_full=args.full,
        )
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
