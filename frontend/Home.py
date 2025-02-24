import asyncio

import streamlit as st
from httpx import AsyncClient, ConnectError, HTTPError, ReadTimeout

# Configure retry settings
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

# Configure page
st.set_page_config(
    page_title="Merlin - YouTube Video Summarizer", page_icon="🧙‍♂️", layout="wide"
)

# Initialize session state
if "client" not in st.session_state:
    st.session_state.client = AsyncClient(base_url="http://backend:8000")

st.title("🧙‍♂️ Merlin - YouTube Video Summarizer")
st.write(
    """
Welcome to Merlin, your AI-powered YouTube video summarizer!
Choose an option from the sidebar to get started.
"""
)

# Add sidebar navigation
st.sidebar.title("Navigation")
st.sidebar.info(
    """
Select a feature from the pages menu above:
- YouTube: Summarize YouTube videos
- More features coming soon...
"""
)

# Display some statistics or recent activities
st.header("Recent Activity")


async def fetch_recent_videos():
    """Fetch and display recent videos with retry logic."""
    for attempt in range(MAX_RETRIES):
        try:
            response = await st.session_state.client.get("/api/v1/youtube/videos")
            response.raise_for_status()
            videos = response.json()

            if videos:
                st.write("Recently summarized videos:")
                for video in videos[:5]:  # Show last 5 videos
                    with st.expander(f"📺 {video['title']}"):
                        st.write(f"Channel: {video['channel']}")
                        st.write(f"Summary: {video['summary']}")
            else:
                st.info(
                    "No videos have been summarized yet. Try summarizing your first video!"
                )
            return

        except (HTTPError, ConnectError, ReadTimeout) as e:
            if attempt == MAX_RETRIES - 1:
                raise Exception(
                    f"Failed to fetch videos after {MAX_RETRIES} attempts: {str(e)}"
                )
            await asyncio.sleep(RETRY_DELAY * (attempt + 1))


try:
    asyncio.run(fetch_recent_videos())
except Exception as e:
    st.error(
        f"Error connecting to the backend service. Please ensure the API is running. Error: {str(e)}"
    )

# Add footer
st.markdown("---")
st.markdown(
    """
<div style='text-align: center'>
    <p>Made with ❤️ by Your Name</p>
</div>
""",
    unsafe_allow_html=True,
)
