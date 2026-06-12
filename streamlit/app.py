"""
Merlin — Streamlit entry point (ARCHIVED).

This is the legacy single-process Streamlit UI, archived under `streamlit/` as
the v3 "engine room" while the FastAPI `api/` + React `web/` frontend is built.
The core library (`merlin/`) stays at the repo root and is shared by both.

Run from the repo root with:  uv run streamlit run streamlit/app.py
"""

from pathlib import Path
import sys

# The core library lives at the repo root (one level up from this archive).
# Ensure it is importable whether launched as `streamlit run streamlit/app.py`
# (from the repo root) or `streamlit run app.py` (with cwd=streamlit/).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from merlin.bootstrap import register_plugins  # noqa: E402
import streamlit as st  # noqa: E402

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
