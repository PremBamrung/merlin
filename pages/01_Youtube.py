# pages/01_Youtube.py
from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy.orm import scoped_session, sessionmaker

# Local imports
from merlin.database.models import SessionLocal, YouTubeVideoSummary, engine, init_db
from merlin.integration.youtube import YouTube
from merlin.utils import check_password, set_layout

set_layout()
# Initialize database
init_db()

session = scoped_session(SessionLocal)

# Load environment variables
load_dotenv()


# Initialize YouTube object
yt = YouTube()


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
        subtitles=subtitles_text,  # Save subtitles text
        date_added=datetime.utcnow(),  # Save the current date and time
    )
    session.add(video_summary)
    session.commit()


def view_summarized_videos():
    st.title("Summarized YouTube Videos")

    # Query all video summaries from the database
    video_summaries = session.query(YouTubeVideoSummary).all()

    if video_summaries:
        data = []
        for video in video_summaries:
            data.append(
                {
                    "Title": video.title,
                    "Video ID ": video.video_id,
                    "Channel": video.channel,
                    "Date": video.date.strftime("%b %d, %Y"),
                    "Views": f"{video.views}",
                    "Duration": video.duration,
                    "Words Count": f"{video.words_count}",
                    "Summary": video.summary,
                    "Date Added": video.date_added.strftime(
                        "%b %d, %Y %H:%M:%S"
                    ),  # including Date Added
                }
            )

        df = pd.DataFrame(data)
        st.dataframe(df)

    else:
        st.write("No videos have been summarized yet.")


def main():
    st.sidebar.title("YouTube Video Summarizer")

    # Add selection tool to sidebar
    options = ["Summarize a Video", "View Summarized Videos"]
    choice = st.sidebar.radio("Select an option", options)

    if choice == "Summarize a Video":
        st.title("🧙‍♂️ YouTube Video Summarizer")

        # Input YouTube video URL
        url = st.text_input("Enter YouTube video URL:", "")

        # Select preferred language for the summary
        lang = st.selectbox(
            "Preferred language for the summary:", ["english", "french", "german"]
        )

        if st.button("Summarize"):
            if url:
                video_id = yt.extract_video_id(url)
                if video_id:
                    # Check for cached video first
                    cached_video = yt.get_cached_video(video_id, session)

                    if cached_video:
                        # Use cached data
                        left_column, right_column = st.columns(2)

                        with left_column:
                            st.write("### Video Information (Cached):")
                            # Display thumbnail image
                            thumbnail_img = yt.extract_thumbnail(video_id)
                            if thumbnail_img:
                                st.image(thumbnail_img, caption="Video Thumbnail")
                            st.write(f"**Title:** {cached_video['title']}")
                            st.write(f"**Channel:** {cached_video['channel']}")
                            st.write(f"**Date:** {cached_video['date']}")
                            st.write(f"**Views:** {cached_video['views']}")
                            st.write(f"**Duration**: {cached_video['duration']}")
                            st.write(
                                f"**Words count:** {cached_video['words_count']:,}"
                            )
                            st.write(f"**Subscribers**: {cached_video['subscribers']}")
                            st.write(f"**Nb Videos**: {cached_video['videos']}")

                        with right_column:
                            st.write("### Summary (Cached):")
                            st.write(cached_video["summary"])

                    else:
                        # Process video as normal
                        video_info = yt.extract_video_info(url)
                        video_info["video_id"] = video_id
                        subtitles = yt.extract_subtitles(video_id, ["en", "fr", "de"])

                        if subtitles:
                            text = yt.extract_text(subtitles)

                            if text:
                                # Define columns to split layout
                                left_column, right_column = st.columns(2)

                                with left_column:
                                    st.write("### Video Information:")
                                    # Display thumbnail image
                                    thumbnail_img = yt.extract_thumbnail(video_id)
                                    if thumbnail_img:
                                        st.image(
                                            thumbnail_img, caption="Video Thumbnail"
                                        )
                                    st.write(f"**Title:** {video_info['title']}")
                                    st.write(f"**Channel:** {video_info['channel']}")
                                    st.write(f"**Date:** {video_info['date']}")
                                    st.write(f"**Views:** {video_info['views']}")
                                    st.write(f"**Duration**: {video_info['duration']}")
                                    st.write(f"**Words count:** {len(text.split()):,}")
                                    st.write(
                                        f"**Subscribers**: {video_info['subscribers']}"
                                    )
                                    st.write(f"**Nb Videos**: {video_info['videos']}")

                                with right_column:
                                    # Generate and display summary
                                    summary_generator = yt.summarize(
                                        subtitles=text,
                                        title=video_info["title"],
                                        channel=video_info["channel"],
                                        lang=lang,
                                        streaming=True,
                                    )
                                    st.write("### Summary:")

                                    summary_text = st.write_stream(summary_generator)

                                    # Save to database
                                    save_video_summary(
                                        video_info, text, summary_text, text
                                    )  # Pass subtitles text

                            else:
                                st.error("Error extracting text from subtitles.")
                        else:
                            st.error("No subtitles found for the given video URL.")
                else:
                    st.error("Invalid YouTube video URL. Please try again.")
            else:
                st.error("Please enter a valid YouTube URL.")
    elif choice == "View Summarized Videos":
        view_summarized_videos()


if __name__ == "__main__":
    main()
    session.remove()  # Close the session when the program ends
