"""Ingest view — submit a YouTube URL for summarisation."""

import streamlit as st

from merlin.knowledge_sources.plugins.youtube.plugin import LANGUAGE_MAP
from merlin.services import ingest
from ui.components.task_panel import task_panel
from ui.state import clear_caches

_LANG_CODES = sorted(LANGUAGE_MAP.keys(), key=lambda c: LANGUAGE_MAP[c])


def _fmt_lang(code: str) -> str:
    return f"{code.upper()} — {LANGUAGE_MAP[code].title()}"


def render() -> None:
    st.title("🧙‍♂️ Ingest")
    st.caption("Summarise a YouTube video into your knowledge base.")

    col_form, col_tasks = st.columns([3, 2], gap="large")

    with col_form:
        url = st.text_input(
            "YouTube URL", placeholder="https://www.youtube.com/watch?v=…"
        )

        languages = st.multiselect(
            "Languages you understand",
            options=_LANG_CODES,
            default=st.session_state.get("ingest_languages", ["en"]),
            format_func=_fmt_lang,
            help=(
                "The summary is generated in the video's language if you "
                "understand it, otherwise in English."
            ),
        )
        st.session_state["ingest_languages"] = languages or ["en"]

        summary_length = st.selectbox(
            "Summary length",
            options=["short", "medium", "long"],
            index=["short", "medium", "long"].index(
                st.session_state.get("ingest_summary_length", "short")
            ),
        )
        st.session_state["ingest_summary_length"] = summary_length

        if st.button("Summarize", type="primary", disabled=not url.strip()):
            try:
                task_id = ingest.submit_youtube(
                    url.strip(), st.session_state["ingest_languages"], summary_length
                )
                clear_caches()
                st.success(f"Queued — task `{task_id[:8]}`. Progress is on the right.")
            except ValueError as exc:
                st.error(str(exc))

    with col_tasks:
        st.subheader("Tasks")
        task_panel()
