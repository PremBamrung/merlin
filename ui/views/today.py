"""Today — entry point: omnibox, key metrics, live ingest queue, recent grid."""

from datetime import date

import streamlit as st

from merlin.services import ingest, library
from ui.components.item_card import item_card
from ui.components.omnibox import omnibox
from ui.components.task_panel import task_panel


def _count(**filters) -> int:
    return library.list_items(page=1, per_page=1, **filters)["total"]


def render() -> None:
    st.session_state["_page"] = "today"

    st.title("Good evening")
    st.caption(date.today().strftime("%A, %B %-d"))

    # --- Omnibox ----------------------------------------------------------
    omnibox()

    st.divider()

    # --- Key metrics ------------------------------------------------------
    c1, c2, c3 = st.columns(3)
    c1.metric("Total items", f"{_count():,}")
    c2.metric("Completed", f"{_count(status='completed'):,}")
    c3.metric("Needs attention", f"{_count(status='failed'):,}")

    # --- Active ingest queue (only when something is in flight) -----------
    if any(
        t["status"] in ("queued", "processing")
        for t in ingest.recent_tasks(limit=8)
    ):
        st.divider()
        st.subheader("Ingesting")
        task_panel()

    st.divider()

    # --- Recently added ---------------------------------------------------
    st.subheader("Recently added")
    recent = library.list_items(page=1, per_page=6)["items"]
    if not recent:
        st.info("Nothing yet — paste a YouTube link above to add your first video.")
        return

    for start in range(0, len(recent), 3):
        cols = st.columns(3)
        for col, item in zip(cols, recent[start : start + 3], strict=False):
            with col:
                item_card(item)
