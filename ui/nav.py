"""
Navigation registry — builds the `st.Page` set once per run and exposes the
pages by name so views can navigate programmatically (e.g. the Today omnibox
routing a question to Chat via `st.switch_page`).
"""

import streamlit as st

from ui.views import chat, ingest, insights, library, today

_PAGES: dict[str, st.Page] | None = None


def build_pages() -> dict[str, st.Page]:
    """Construct (once per run) and return the page registry keyed by name."""
    global _PAGES
    _PAGES = {
        "today": st.Page(
            today.render,
            title="Today",
            icon=":material/home:",
            url_path="today",
            default=True,
        ),
        "ingest": st.Page(
            ingest.render,
            title="Ingest",
            icon=":material/add_circle:",
            url_path="ingest",
        ),
        "library": st.Page(
            library.render,
            title="Library",
            icon=":material/grid_view:",
            url_path="library",
        ),
        "chat": st.Page(
            chat.render,
            title="Chat",
            icon=":material/forum:",
            url_path="chat",
        ),
        "insights": st.Page(
            insights.render,
            title="Insights",
            icon=":material/insights:",
            url_path="insights",
        ),
    }
    return _PAGES


def page(name: str) -> st.Page:
    """Return a built page by name (builds the set lazily if needed)."""
    pages = _PAGES if _PAGES is not None else build_pages()
    return pages[name]


def goto(name: str) -> None:
    """Switch to a named page."""
    st.switch_page(page(name))


def open_reader(item_id: str) -> None:
    """Request the Reader for an item (callback-safe — state mutation only).

    This is invoked from `on_click` callbacks, where navigation primitives
    (`st.switch_page` / `st.rerun`) are no-ops. So we only record the intent in
    `session_state`; `app.py` performs the actual routing in the main script
    body (mirrors `?item=` to the URL and switches to the Library page, which
    renders the Reader when an item is selected).
    """
    st.session_state["open_item"] = item_id
