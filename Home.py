import re
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from sqlalchemy.orm import scoped_session

from merlin.database.models import SessionLocal, YouTubeVideoSummary, init_db
from merlin.integration.youtube import YouTube
from merlin.llm.openrouter import llm
from merlin.utils import logger, set_layout


def parse_views(views_str):
    """Parse views string to integer."""
    return int(views_str.replace(",", "").replace(" views", ""))


def parse_date(date_str):
    """Parse date string to datetime object."""
    try:
        return datetime.strptime(date_str, "%b %d, %Y")
    except ValueError:
        return datetime.strptime(date_str, "%d/%m/%Y")


def save_video_summary(video_info, text, summary_text, subtitles_text):
    """Save video summary to database."""
    views = parse_views(video_info["views"])
    date = parse_date(video_info["date"])

    video_summary = YouTubeVideoSummary(
        video_id=video_info["video_id"],
        title=video_info["title"],
        channel=video_info["channel"],
        date=date,
        views=views,
        duration=video_info["duration"],
        words_count=len(text.split()),
        subscribers=video_info["subscribers"],
        videos=video_info["videos"],
        summary=summary_text,
        subtitles=subtitles_text,
        date_added=datetime.utcnow(),
    )
    session.add(video_summary)
    session.commit()


set_layout()
init_db()

# Initialize session and YouTube
session = scoped_session(SessionLocal)
yt = YouTube()

load_dotenv("merlin/.env")


st.title("🧙‍♂️ Merlin")
st.caption("🚀 A Streamlit chatbot powered by OpenAI")

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "How can I help you?"}
    ]

# Add a button in the sidebar to clear the conversation
if st.sidebar.button("Clear Conversation"):
    st.session_state["messages"] = [
        {"role": "assistant", "content": "How can I help you?"}
    ]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])


def process_youtube_url(url: str) -> str:
    """Process YouTube URL and return formatted summary with metadata."""
    video_id = yt.extract_video_id(url)
    if not video_id:
        return "Invalid YouTube URL. Please provide a valid YouTube video link."

    # Check cache first
    cached_video = yt.get_cached_video(video_id, session)
    if cached_video:
        logger.info(f"Using cached summary for video ID: {video_id}")
        return f"""📺 Video Information:
• Title: {cached_video['title']}
• Channel: {cached_video['channel']}
• Duration: {cached_video['duration']}
• Views: {cached_video['views']}
• Published: {cached_video['date']}

📝 Summary:
{cached_video['summary']}"""

    # Process new video
    try:
        video_info = yt.extract_video_info(url)
        if not video_info:
            return "Failed to extract video information. Please try again."

        subtitles = yt.extract_subtitles(video_id, ["en", "fr", "de"])
        if not subtitles:
            return "No subtitles found for this video."

        text = yt.extract_text(subtitles)
        if not text:
            return "Failed to extract text from subtitles."

        # Generate summary
        summary_text = ""
        for chunk in yt.summarize(
            subtitles=text,
            title=video_info["title"],
            channel=video_info["channel"],
            lang="english",
            streaming=True,
        ):
            summary_text += chunk

        # Save to database
        save_video_summary(video_info, text, summary_text, text)
        logger.info(f"Saved new summary for video ID: {video_id}")

        return f"""📺 Video Information:
• Title: {video_info['title']}
• Channel: {video_info['channel']}
• Duration: {video_info['duration']}
• Views: {video_info['views']}
• Published: {video_info['date']}

📝 Summary:
{summary_text}"""
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        return f"An error occurred while processing the video: {str(e)}"


if prompt := st.chat_input():
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):
        # Check for YouTube URL in the prompt
        youtube_url_match = re.search(
            r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[a-zA-Z0-9_-]+",
            prompt,
        )

        if youtube_url_match:
            youtube_url = youtube_url_match.group(0)
            response = process_youtube_url(youtube_url)
            st.write(response)
        else:
            response = st.write_stream(llm.stream(st.session_state.messages))

    st.session_state.messages.append({"role": "assistant", "content": response})
