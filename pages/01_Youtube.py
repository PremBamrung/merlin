import os

import streamlit as st
from dotenv import load_dotenv

from merlin.integration.youtube import YouTube

# Load environment variables
load_dotenv()

# Initialize YouTube object
yt = YouTube(
    azure_model_deployment=os.getenv("AZURE_MODEL_DEPLOYMENT"),
    azure_endpoint=os.getenv("AZURE_ENDPOINT"),
    azure_key=os.getenv("AZURE_KEY"),
    azure_api_version=os.getenv("AZURE_API_VERSION"),
)


def main():
    st.title("YouTube Video Summarizer")

    # Input YouTube video URL
    url = st.text_input("Enter YouTube video URL:", "")

    # Select preferred language for the summary
    lang = st.selectbox(
        "Preferred language for the summary:", ["english", "french", "german"]
    )

    if st.button("Summarize"):
        if url:
            video_id = yt.extract_video_id(url)
            video_info = yt.extract_video_info(url)

            if video_id:
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
                                st.image(thumbnail_img, caption="Video Thumbnail")
                            st.write(f"**Title:** {video_info['title']}")
                            st.write(f"**Channel:** {video_info['channel']}")
                            st.write(f"**Date:** {video_info['date']}")
                            st.write(f"**Views:** {video_info['views']}")
                            st.write(
                                f"**Duration**: {video_info['duration']}"
                            )  # Print video duration

                            st.write(f"**Words count:** {len(text.split()):,}")
                            st.write(f"**Subscribers**: {video_info['subscribers']}")
                            st.write(f"**Nb Videos**: {video_info['videos']}")

                        with right_column:
                            # Generate and display summary
                            summary = yt.summarize(
                                subtitles=text, lang=lang, streaming=True
                            )
                            st.write("### Summary:")
                            st.write_stream(summary)
                    else:
                        st.error("Error extracting text from subtitles.")
                else:
                    st.error("No subtitles found for the given video URL.")
            else:
                st.error("Invalid YouTube video URL. Please try again.")
        else:
            st.error("Please enter a valid YouTube URL.")


if __name__ == "__main__":
    main()
