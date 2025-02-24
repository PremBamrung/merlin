"""YouTube video summarization page."""

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from merlin.database.models import init_db
from merlin.database.repositories import VideoRepository
from merlin.integration.youtube import YouTubeService
from merlin.utils import set_layout

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

        # Clear URL from session state after using it
        if "url" in st.session_state:
            del st.session_state["url"]

        # Select preferred language for the summary
        lang = st.selectbox(
            "Preferred language for the summary:", ["english", "french", "german"]
        )

        if st.button("Summarize"):
            if url:
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
                                    # Store URL in session state
                                    st.session_state["url"] = url
                                    st.success("Cache cleared. Regenerating summary...")
                                    st.rerun()

                    else:
                        # Process video
                        result = yt.process_video(url, lang=lang, streaming=True)

                        if result:
                            # Define columns to split layout
                            left_column, right_column = st.columns(2)

                            with left_column:
                                display_video_info(result["video_info"])

                            with right_column:
                                st.write("### Summary:")
                                summary_text = st.write_stream(
                                    result["summary_generator"]
                                )

                                # Save to database after streaming
                                yt.db.execute_with_session(
                                    lambda session: VideoRepository.save_video_summary(
                                        session,
                                        result["video_info"],
                                        result["text"],
                                        summary_text,
                                        result["text"],
                                    )
                                )
                        else:
                            st.error("Failed to process video. Please try again.")
                else:
                    st.error("Invalid YouTube video URL. Please try again.")
            else:
                st.error("Please enter a valid YouTube URL.")

    elif choice == "View Summarized Videos":
        view_summarized_videos()


if __name__ == "__main__":
    main()
