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

# Build the navigation registry (pages are also reachable by name from views,
# e.g. the Today omnibox routing a question to Chat).
from ui.nav import build_pages  # noqa: E402

pages = build_pages()
navigation = st.navigation(list(pages.values()))
navigation.run()
