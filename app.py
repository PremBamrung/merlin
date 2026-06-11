"""
Merlin — Streamlit entry point.

Run with:  uv run streamlit run app.py

A single Streamlit (Starlette/Uvicorn) process. The UI imports the `merlin`
core library directly — there is no separate backend service.
"""

import streamlit as st

from merlin.bootstrap import register_plugins

st.set_page_config(page_title="Merlin", page_icon="🧙", layout="wide")

# Register knowledge-source plugins once (idempotent across reruns).
register_plugins()

# Import views after page config / bootstrap.
from ui.views import chat, ingest, library, today  # noqa: E402

navigation = st.navigation(
    [
        st.Page(
            today.render,
            title="Today",
            icon=":material/home:",
            url_path="today",
            default=True,
        ),
        st.Page(
            ingest.render,
            title="Ingest",
            icon=":material/add_circle:",
            url_path="ingest",
        ),
        st.Page(
            library.render,
            title="Library",
            icon=":material/grid_view:",
            url_path="library",
        ),
        st.Page(chat.render, title="Chat", icon=":material/forum:", url_path="chat"),
    ]
)
navigation.run()
