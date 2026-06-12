"""Today omnibox — one input that ingests a link or asks the knowledge base.

`omnibox_route()` is a pure helper (no Streamlit) so the URL-vs-question routing
is unit-testable on its own.
"""

import re

import streamlit as st

from merlin.services import ingest
from ui.state import clear_caches, queue_question

# Looks-like-a-link heuristic: a scheme, a known host, or a bare domain/path.
_URL_RE = re.compile(
    r"(https?://|www\.|youtu\.?be|youtube\.com|\b\w[\w-]*\.\w{2,}(/|$))",
    re.IGNORECASE,
)


def omnibox_route(text: str) -> tuple[str | None, str]:
    """Classify omnibox input → ('ingest'|'ask'|None, normalised_text)."""
    text = (text or "").strip()
    if not text:
        return None, ""
    if _URL_RE.search(text):
        return "ingest", text
    return "ask", text


def omnibox() -> None:
    """Render the omnibox. Routes a link to ingest, a question to Chat."""
    from ui import nav  # lazy: avoids today→omnibox→nav→views import cycle

    with st.form("omnibox", clear_on_submit=True, border=False):
        c1, c2 = st.columns([6, 1], vertical_alignment="bottom")
        with c1:
            text = st.text_input(
                "omnibox",
                placeholder="Paste a YouTube link to ingest, or ask your library…",
                label_visibility="collapsed",
            )
        with c2:
            submitted = st.form_submit_button("Send ↵", type="primary", width="stretch")

    st.caption("Paste a link to ingest · type a question to ask your library")

    if not submitted:
        return

    kind, payload = omnibox_route(text)
    if kind == "ingest":
        try:
            langs = st.session_state.get("ingest_languages", ["en"])
            length = st.session_state.get("ingest_summary_length", "short")
            task_id = ingest.submit_youtube(payload, langs, length)
            clear_caches()
            st.toast(f"Queued ingest — task {task_id[:8]}")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    elif kind == "ask":
        queue_question(payload)
        nav.goto("chat")
