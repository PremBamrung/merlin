"""YouTube video summarization page."""

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from merlin.database.models import init_db
from merlin.database.repositories import VideoRepository
from merlin.integration.youtube import YouTubeService
from merlin.utils import logger, set_layout

# Initialize layout
set_layout()

# Initialize database
init_db()

# Load environment variables
load_dotenv()

# Initialize YouTube service
yt = YouTubeService()


def view_summarized_videos():
    """Display all summarized videos in a table."""
    st.title("Summarized YouTube Videos")

    videos = yt.get_all_videos()
    if videos:
        data = []
        for video in videos:
            data.append(
                {
                    "Title": video.title,
                    "Video ID": video.video_id,
                    "Channel": video.channel,
                    "Date": video.date.strftime("%b %d, %Y"),
                    "Views": f"{video.views:,}",
                    "Duration": video.duration,
                    "Words Count": f"{video.words_count:,}",
                    "Summary": video.summary,
                    "Date Added": video.date_added.strftime("%b %d, %Y %H:%M:%S"),
                }
            )
        df = pd.DataFrame(data)
        st.dataframe(df)
    else:
        st.write("No videos have been summarized yet.")


def display_video_info(video_info: dict, cached: bool = False):
    """Display video information in the UI."""
    st.write(f"### Video Information{'(Cached)' if cached else ''}:")

    # Display thumbnail
    thumbnail_img = yt.extract_thumbnail(video_info["video_id"])
    if thumbnail_img:
        st.image(thumbnail_img, caption="Video Thumbnail")

    # Display metadata
    st.write(f"**Title:** {video_info['title']}")
    st.write(f"**Channel:** {video_info['channel']}")
    st.write(f"**Date:** {video_info['date']}")
    st.write(f"**Views:** {video_info['views']}")
    st.write(f"**Duration:** {video_info['duration']}")
    st.write(f"**Words count:** {video_info.get('words_count', 'N/A')}")
    st.write(f"**Subscribers:** {video_info['subscribers']}")
    st.write(f"**Videos:** {video_info['videos']}")


def filter_videos(videos, search_query=None, selected_tags=None):
    """Filter videos based on search query and tags."""
    if not videos:
        return []

    filtered_videos = videos

    if search_query:
        search_query = search_query.lower()
        filtered_videos = [
            v
            for v in filtered_videos
            if search_query in v.title.lower()
            or search_query in v.channel.lower()
            or search_query in (v.summary or "").lower()
            or search_query in (v.tags or "").lower()
        ]

    if selected_tags:
        filtered_videos = [
            v
            for v in filtered_videos
            if v.tags and any(tag in v.tags.split(",") for tag in selected_tags)
        ]

    return filtered_videos


def main():
    """Main application entry point."""
    st.sidebar.title("YouTube Video Summarizer")

    # Add selection tool to sidebar
    options = ["Summarize a Video", "View Summarized Videos"]
    choice = st.sidebar.radio("Select an option", options)

    if choice == "Summarize a Video":
        st.title("🧙‍♂️ YouTube Video Summarizer")

        # Input YouTube video URL
        url = st.text_input("Enter YouTube video URL:", st.session_state.get("url", ""))

        # Add configuration options in columns
        col1, col2 = st.columns(2)

        with col1:
            # Select preferred language for the summary
            lang = st.selectbox(
                "Preferred language:",
                ["english", "french", "german"],
                index=(
                    ["english", "french", "german"].index(
                        st.session_state.get("lang", "english")
                    )
                    if "lang" in st.session_state
                    else 0
                ),
            )

            # Add summary length option
            summary_length = st.selectbox(
                "Summary length:",
                ["short", "medium", "long"],
                index=(
                    ["short", "medium", "long"].index(
                        st.session_state.get("summary_length", "short")
                    )
                    if "summary_length" in st.session_state
                    else 0
                ),
                help="Short: key points only, Medium: balanced, Long: detailed analysis",
            )

        with col2:
            # Add tags input
            tags = st.text_input(
                "Tags (comma-separated):",
                help="Add tags to organize your summaries (e.g., tech, news, tutorial)",
            )

        if st.button("Summarize"):
            if not url:
                st.error("Please enter a valid YouTube URL.")
                return

            # Show loading spinner during processing
            with st.spinner("Processing video... This may take a few minutes."):
                video_id = yt.video_extractor.extract_video_id(url)
                if video_id:
                    # Check for cached video first
                    cached_video = yt.get_cached_video(video_id)

                    if cached_video:
                        # Use cached data
                        left_column, right_column = st.columns(2)

                        with left_column:
                            display_video_info(cached_video, cached=True)

                        with right_column:
                            st.write("### Summary (Cached):")
                            st.write(cached_video["summary"])

                            # Add redo summary button
                            if st.button("Redo Summary", key=f"redo_{video_id}"):
                                if yt.delete_cached_video(video_id):
                                    # Store URL and parameters in session state
                                    st.session_state["url"] = url
                                    st.session_state["lang"] = lang
                                    st.session_state["summary_length"] = summary_length
                                    st.session_state["tags"] = tags
                                    st.success("Cache cleared. Regenerating summary...")
                                    st.rerun()
                    else:
                        try:
                            # Process video with new parameters
                            summary_text = ""
                            video_info = None
                            text = None
                            topics = {}
                            timestamps = {}

                            # Create columns for layout
                            left_column, right_column = st.columns(2)

                            # Process the video and stream the summary
                            for response in yt.process_video(
                                url,
                                lang=lang,
                                summary_length=summary_length,
                                streaming=True,
                            ):
                                if response.get("type") == "metadata":
                                    # Initial metadata received
                                    video_info = response["video_info"]
                                    text = response["text"]

                                    with left_column:
                                        display_video_info(video_info)

                                    with right_column:
                                        st.write("### Summary:")
                                        summary_placeholder = st.empty()

                                elif response.get("type") == "chunk":
                                    # Summary chunk received
                                    summary_text += response["content"]
                                    summary_placeholder.write(summary_text)

                                elif response.get("type") == "summary_metadata":
                                    # Final metadata received
                                    summary_text = response["summary"]
                                    topics = response.get("topics", {})
                                    timestamps = response.get("timestamps", {})

                                    with right_column:
                                        if topics:
                                            st.write("### Topics and Timestamps:")
                                            for topic, timestamp in topics.items():
                                                st.write(f"- {topic} [{timestamp}]")

                                        # Save to database with new fields
                                        yt.db.execute_with_session(
                                            lambda session: VideoRepository.save_video_summary(
                                                session,
                                                video_info,
                                                text,
                                                summary_text,
                                                text,
                                                tags=tags,
                                                summary_length=summary_length,
                                                topics=topics,
                                                timestamps=timestamps,
                                            )
                                        )

                                        st.success("Video processed successfully!")

                                elif response.get("type") == "error":
                                    st.error(
                                        f"An error occurred: {response['message']}"
                                    )
                                    break
                            else:
                                st.error(
                                    "Failed to process video. The video might be unavailable or have no subtitles."
                                )
                        except Exception as e:
                            st.error(f"An error occurred: {str(e)}")
                            # Log the error for debugging
                            logger.error(f"Error processing video: {str(e)}")
                else:
                    st.error("Invalid YouTube video URL. Please try again.")

    elif choice == "View Summarized Videos":
        st.title("Summarized YouTube Videos")

        # Add search and filter options
        col1, col2 = st.columns([2, 1])

        with col1:
            search_query = st.text_input(
                "Search videos:", placeholder="Search by title, channel, content..."
            )

        with col2:
            # Get all unique tags
            all_tags = set()
            videos = yt.get_all_videos()
            for video in videos:
                if video.tags:
                    all_tags.update(tag.strip() for tag in video.tags.split(","))

            selected_tags = st.multiselect(
                "Filter by tags:", sorted(list(all_tags)) if all_tags else []
            )

        # Filter and display videos
        filtered_videos = filter_videos(videos, search_query, selected_tags)

        if filtered_videos:
            data = []
            for video in filtered_videos:
                data.append(
                    {
                        "Title": video.title,
                        "Channel": video.channel,
                        "Date": video.date.strftime("%b %d, %Y"),
                        "Views": f"{video.views:,}",
                        "Duration": video.duration,
                        "Length": video.summary_length or "N/A",
                        "Tags": video.tags or "N/A",
                        "Summary": video.summary,
                    }
                )
            df = pd.DataFrame(data)
            st.dataframe(df)
        else:
            if search_query or selected_tags:
                st.info("No videos found matching your search criteria.")
            else:
                st.info("No videos have been summarized yet.")


if __name__ == "__main__":
    main()
