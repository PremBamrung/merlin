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

# Card clicks set `open_item` in their on_click callback — navigation
# (st.switch_page / st.rerun) is a no-op inside callbacks, so we route here in
# the main script body instead. Mirror to `?item=` for a shareable URL and jump
# to the Library (which renders the Reader when an item is selected).
_open_item = st.session_state.get("open_item")
if _open_item:
    st.query_params["item"] = _open_item
    if navigation.url_path != "library":
        st.switch_page(pages["library"])

navigation.run()
