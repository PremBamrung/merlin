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
                    "Title": video["title"],
                    "Video ID": video["video_id"],
                    "Channel": video["channel"],
                    "Published Date": video["date"].strftime("%b %d, %Y"),
                    "Date Added": video["date_added"].strftime("%b %d, %Y %H:%M:%S"),
                    "Views": f"{video['views']:,}",
                    "Duration": video["duration"],
                    "Words Count": f"{video.get('words_count', 0):,}",
                    "LLM Model": video.get("llm_model") or "N/A",
                    "Summary": video.get("summary"),
                }
            )
        df = pd.DataFrame(data)
        st.dataframe(df)
    else:
        st.write("No videos have been summarized yet.")


def display_video_info(video_info: dict, cached: bool = False):
    """Display video information in the UI."""
    st.write(f"### Video Information{'(Cached)' if cached else ''}:")

    # Create 2-column layout: thumbnail on left, info on right
    col_thumb, col_info = st.columns([1, 2])

    with col_thumb:
        # Display thumbnail
        thumbnail_img = yt.extract_thumbnail(video_info["video_id"])
        if thumbnail_img:
            st.image(thumbnail_img, caption="Video Thumbnail")

    with col_info:
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
            if search_query in v["title"].lower()
            or search_query in v["channel"].lower()
            or search_query in (v.get("summary") or "").lower()
            or search_query in (v.get("tags") or "").lower()
        ]

    if selected_tags:
        filtered_videos = [
            v
            for v in filtered_videos
            if v.get("tags")
            and any(tag in v["tags"].split(",") for tag in selected_tags)
        ]

    return filtered_videos


def main():
    """Main application entry point."""
    st.sidebar.title("YouTube Video Summarizer")

    # Add selection tool to sidebar
    options = ["Summarize a Video", "View Summarized Videos"]
    # Use session state to persist choice, defaulting to stored value or first option
    if "choice" not in st.session_state:
        st.session_state["choice"] = options[0]
    choice = st.sidebar.radio(
        "Select an option", options, index=options.index(st.session_state["choice"])
    )
    st.session_state["choice"] = choice

    if choice == "Summarize a Video":
        st.title("🧙‍♂️ YouTube Video Summarizer")

        # Input YouTube video URL
        url = st.text_input("Enter YouTube video URL:", st.session_state.get("url", ""))

        # Add configuration options
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

        # Set tags to empty string (tags input removed)
        tags = ""

        # Check if URL has a cached summary and show redo option
        cached_video_info = None
        auto_summarize = False
        if url:
            video_id = yt.video_extractor.extract_video_id(url)
            if video_id:
                cached_video_info = yt.get_cached_video(video_id)
                if cached_video_info:
                    st.info(
                        f"📋 This video already has a cached summary (Length: {cached_video_info.get('summary_length', 'medium')}, Language: {cached_video_info.get('lang', 'english')})"
                    )
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button(
                            "🔄 Redo Summary",
                            key="redo_summary_main",
                            help="Clear the cached summary and regenerate with current settings",
                        ):
                            if yt.delete_cached_video(video_id):
                                st.session_state["url"] = url
                                st.session_state["lang"] = lang
                                st.session_state["summary_length"] = summary_length
                                st.session_state["tags"] = tags
                                st.session_state["auto_summarize"] = True
                                st.success("Cache cleared. Regenerating summary...")
                                st.rerun()
                    with col_btn2:
                        if st.button(
                            "View Cached Summary",
                            key="view_cached_main",
                            help="View the existing cached summary",
                        ):
                            st.session_state["view_cached"] = video_id
                            st.rerun()

        # Auto-summarize if redo was triggered
        if st.session_state.get("auto_summarize", False):
            st.session_state["auto_summarize"] = False
            auto_summarize = True

        # Show cached summary if view button was clicked
        if st.session_state.get("view_cached"):
            view_video_id = st.session_state.pop("view_cached")
            cached_video = yt.get_cached_video(view_video_id)
            if cached_video:
                display_video_info(cached_video, cached=True)
                st.write("### Summary (Cached):")
                st.write(cached_video["summary"])
                if cached_video.get("topics"):
                    st.write("### Topics and Timestamps:")
                    for topic, timestamp in cached_video["topics"].items():
                        st.write(f"- {topic} [{timestamp}]")
                if st.button(
                    "🔄 Redo Summary",
                    key=f"redo_view_{view_video_id}",
                    help="Regenerate the summary with updated prompts or settings",
                ):
                    if yt.delete_cached_video(view_video_id):
                        st.session_state["url"] = url
                        st.session_state["lang"] = lang
                        st.session_state["summary_length"] = summary_length
                        st.session_state["tags"] = tags
                        st.session_state["auto_summarize"] = True
                        st.success("Cache cleared. Regenerating summary...")
                        st.rerun()

        if st.button("Summarize") or auto_summarize:
            if not url:
                st.error("Please enter a valid YouTube URL.")
                return

            # Show loading spinner during processing
            with st.spinner("Processing video... This may take a few minutes."):
                video_id = yt.video_extractor.extract_video_id(url)
                if video_id:
                    # Check for cached video first (unless we're auto-summarizing after clearing cache)
                    cached_video = (
                        None if auto_summarize else yt.get_cached_video(video_id)
                    )

                    if cached_video:
                        # Use cached data
                        display_video_info(cached_video, cached=True)
                        st.write("### Summary (Cached):")
                        st.write(cached_video["summary"])

                        # Display topics if available
                        if cached_video.get("topics"):
                            st.write("### Topics and Timestamps:")
                            for topic, timestamp in cached_video["topics"].items():
                                st.write(f"- {topic} [{timestamp}]")

                        # Add redo summary button
                        if st.button(
                            "🔄 Redo Summary",
                            key=f"redo_cached_{video_id}",
                            help="Regenerate the summary with updated prompts or settings",
                        ):
                            if yt.delete_cached_video(video_id):
                                # Store URL and parameters in session state
                                st.session_state["url"] = url
                                st.session_state["lang"] = lang
                                st.session_state["summary_length"] = summary_length
                                st.session_state["tags"] = tags
                                st.session_state["redo_summary"] = True
                                st.success(
                                    "Cache cleared. Regenerating summary with current settings..."
                                )
                                st.rerun()
                    else:
                        try:
                            # Process video with new parameters
                            summary_text = ""
                            video_info = None
                            text = None
                            topics = {}
                            timestamps = {}

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

                                    display_video_info(video_info)
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
                                    llm_model = response.get("llm_model", "unknown")

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
                                            llm_model=llm_model,
                                            topics=topics,
                                            timestamps=timestamps,
                                        )
                                    )

                                    st.success("Video processed successfully!")

                                    # Add redo summary button
                                    if st.button(
                                        "🔄 Redo Summary",
                                        key=f"redo_summary_{video_id}",
                                        help="Regenerate the summary with updated prompts or settings",
                                    ):
                                        if yt.delete_cached_video(video_id):
                                            # Store URL and parameters in session state
                                            st.session_state["url"] = url
                                            st.session_state["lang"] = lang
                                            st.session_state["summary_length"] = (
                                                summary_length
                                            )
                                            st.session_state["tags"] = tags
                                            st.session_state["redo_summary"] = True
                                            st.success(
                                                "Summary cleared. Regenerating with current settings..."
                                            )
                                            st.rerun()

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
                if video.get("tags"):
                    all_tags.update(tag.strip() for tag in video["tags"].split(","))

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
                        "Title": video["title"],
                        "Channel": video["channel"],
                        "Published Date": video["date"].strftime("%b %d, %Y"),
                        "Date Added": video["date_added"].strftime(
                            "%b %d, %Y %H:%M:%S"
                        ),
                        "Views": f"{video['views']:,}",
                        "Duration": video["duration"],
                        "Length": video.get("summary_length") or "N/A",
                        "LLM Model": video.get("llm_model") or "N/A",
                        "Tags": video.get("tags") or "N/A",
                        "Summary": video.get("summary"),
                    }
                )
            df = pd.DataFrame(data)
            st.dataframe(df)

            # Add section to redo summary for a specific video
            st.divider()
            st.subheader("Redo Summary")

            # Create a dropdown to select video
            video_options = {
                f"{v['title']} ({v['channel']})": v["video_id"] for v in filtered_videos
            }

            if video_options:
                selected_video_title = st.selectbox(
                    "Select a video to redo its summary:",
                    options=list(video_options.keys()),
                    help="Choose a video to regenerate its summary with updated prompts or settings",
                )

                selected_video_id = video_options[selected_video_title]
                selected_video = next(
                    v for v in filtered_videos if v["video_id"] == selected_video_id
                )

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(
                        f"**Current Language:** {selected_video.get('lang', 'english')}"
                    )
                with col2:
                    st.write(
                        f"**Current Length:** {selected_video.get('summary_length', 'medium')}"
                    )
                with col3:
                    st.write(f"**Current Tags:** {selected_video.get('tags', 'N/A')}")

                if st.button(
                    "🔄 Redo Summary for Selected Video",
                    key="redo_from_list",
                    help="This will delete the current summary and switch to the 'Summarize a Video' page to regenerate",
                ):
                    if yt.delete_cached_video(selected_video_id):
                        # Construct YouTube URL from video ID
                        youtube_url = (
                            f"https://www.youtube.com/watch?v={selected_video_id}"
                        )
                        # Store in session state and switch to summarize page
                        st.session_state["url"] = youtube_url
                        st.session_state["lang"] = selected_video.get("lang", "english")
                        st.session_state["summary_length"] = selected_video.get(
                            "summary_length", "medium"
                        )
                        st.session_state["tags"] = selected_video.get("tags", "")
                        st.session_state["redo_summary"] = True
                        st.success("Summary cleared. Switching to summarize page...")
                        # Change the radio selection to "Summarize a Video"
                        st.session_state["choice"] = "Summarize a Video"
                        st.rerun()
                    else:
                        st.error("Failed to delete the summary. Please try again.")
        else:
            if search_query or selected_tags:
                st.info("No videos found matching your search criteria.")
            else:
                st.info("No videos have been summarized yet.")


if __name__ == "__main__":
    main()
