import asyncio
from typing import Optional

import streamlit as st
from httpx import AsyncClient, ConnectError, HTTPError, ReadTimeout

# Initialize session state for the client if not exists
if "client" not in st.session_state:
    st.session_state.client = AsyncClient(base_url="http://backend:8000", timeout=30.0)

# Configure retry settings
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

st.title("🎥 YouTube Video Summarizer")


async def process_video(url: str, language: str, summary_length: str, tags: str):
    """Process video through the API with retries."""
    for attempt in range(MAX_RETRIES):
        try:
            response = await st.session_state.client.post(
                "/api/v1/youtube/videos/process",
                json={
                    "url": url,
                    "language": language,
                    "summary_length": summary_length,
                    "tags": tags,
                },
            )
            response.raise_for_status()
            return response.json()
        except (HTTPError, ConnectError, ReadTimeout) as e:
            if attempt == MAX_RETRIES - 1:
                raise Exception(
                    f"Failed to process video after {MAX_RETRIES} attempts: {str(e)}"
                )
            await asyncio.sleep(RETRY_DELAY * (attempt + 1))


async def search_videos(query: Optional[str] = None, tags: Optional[str] = None):
    """Search videos through the API with retries."""
    params = {}
    if query:
        params["query"] = query
    if tags:
        params["tags"] = tags.split(",")

    for attempt in range(MAX_RETRIES):
        try:
            response = await st.session_state.client.get(
                "/api/v1/youtube/videos", params=params
            )
            response.raise_for_status()
            return response.json()
        except (HTTPError, ConnectError, ReadTimeout) as e:
            if attempt == MAX_RETRIES - 1:
                raise Exception(
                    f"Failed to search videos after {MAX_RETRIES} attempts: {str(e)}"
                )
            await asyncio.sleep(RETRY_DELAY * (attempt + 1))


# Input section
with st.form("youtube_form"):
    url = st.text_input("Enter YouTube video URL:")

    col1, col2 = st.columns(2)

    with col1:
        language = st.selectbox(
            "Preferred language:", ["english", "french", "german"], index=0
        )

        summary_length = st.selectbox(
            "Summary length:",
            ["short", "medium", "long"],
            index=0,
            help="Short: key points only, Medium: balanced, Long: detailed analysis",
        )

    with col2:
        tags = st.text_input(
            "Tags (comma-separated):",
            help="Add tags to organize your summaries (e.g., tech, news, tutorial)",
        )

    submitted = st.form_submit_button("Summarize")


async def process_submitted_video():
    if submitted and url:
        try:
            with st.spinner("Processing video... This may take a few minutes."):
                # Make API request to process video
                result = await process_video(url, language, summary_length, tags)
                video = result["video"]

                # Display results in columns
                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("Video Information")
                    st.write(f"**Title:** {video['title']}")
                    st.write(f"**Channel:** {video['channel']}")
                    st.write(f"**Duration:** {video['duration']}")
                    st.write(f"**Views:** {video['views']:,}")
                    if video["subscribers"]:
                        st.write(f"**Channel Subscribers:** {video['subscribers']}")

                with col2:
                    st.subheader("Summary")
                    st.write(video["summary"])

                    if video.get("topics"):
                        st.subheader("Main Topics")
                        for topic, timestamp in video["topics"].items():
                            st.write(f"- {topic} [{timestamp}]")

                # Show full transcript in expander
                with st.expander("Show Full Transcript"):
                    st.text(video["transcript"])

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")


if submitted and url:
    asyncio.run(process_submitted_video())
else:
    if submitted:
        st.warning("Please enter a YouTube URL.")

# Search and filter section
st.markdown("---")
st.subheader("Search Summarized Videos")

search_query = st.text_input("Search by title, channel, or content:")
tag_filter = st.text_input("Filter by tags (comma-separated):")


async def search_and_display_videos():
    if search_query or tag_filter:
        try:
            # Make API request to search videos
            videos = await search_videos(search_query, tag_filter)

            if videos:
                for video in videos:
                    with st.expander(f"📺 {video['title']}"):
                        st.write(f"**Channel:** {video['channel']}")
                        st.write(f"**Summary Length:** {video['summary_length']}")
                        if video.get("tags"):
                            st.write(f"**Tags:** {video['tags']}")
                        st.write("**Summary:**")
                        st.write(video["summary"])
            else:
                st.info("No videos found matching your search criteria.")

        except Exception as e:
            st.error(f"An error occurred while searching: {str(e)}")


if search_query or tag_filter:
    asyncio.run(search_and_display_videos())

# Add some spacing at the bottom
st.markdown("---")
st.markdown("<br>", unsafe_allow_html=True)
