"""Ingest view — the power entry: full control over a YouTube ingest."""

import streamlit as st

from merlin.knowledge_sources.plugins.youtube.plugin import LANGUAGE_MAP
from merlin.services import ingest
from ui.components.task_panel import task_panel
from ui.state import clear_caches

_LANG_CODES = sorted(LANGUAGE_MAP.keys(), key=lambda c: LANGUAGE_MAP[c])
_LENGTHS = ["short", "medium", "long"]


def _fmt_lang(code: str) -> str:
    return f"{code.upper()} — {LANGUAGE_MAP[code].title()}"


def render() -> None:
    st.session_state["_page"] = "ingest"
    st.title("Ingest")
    st.caption("Summarise a YouTube video into your knowledge base.")

    with st.container(border=True):
        url = st.text_input(
            "YouTube URL", placeholder="https://www.youtube.com/watch?v=…"
        )

        c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
        with c1:
            length = st.segmented_control(
                "Summary length",
                options=_LENGTHS,
                default=st.session_state.get("ingest_summary_length", "short"),
            )
            st.session_state["ingest_summary_length"] = length or "short"
        with c2:
            submit = st.button(
                "🧙 Summarize",
                type="primary",
                width="stretch",
                disabled=not url.strip(),
            )

        with st.expander("Advanced — languages you understand"):
            languages = st.multiselect(
                "Languages",
                options=_LANG_CODES,
                default=st.session_state.get("ingest_languages", ["en"]),
                format_func=_fmt_lang,
                help=(
                    "The summary is generated in the video's language if you "
                    "understand it, otherwise in English."
                ),
                label_visibility="collapsed",
            )
            st.session_state["ingest_languages"] = languages or ["en"]

    if submit:
        try:
            task_id = ingest.submit_youtube(
                url.strip(),
                st.session_state["ingest_languages"],
                st.session_state["ingest_summary_length"],
            )
            clear_caches()
            st.success(f"Queued — task `{task_id[:8]}`. Progress below.")
        except ValueError as exc:
            st.error(str(exc))

    st.divider()
    st.subheader("Tasks")
    task_panel()
