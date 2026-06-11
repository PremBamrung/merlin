"""Today view — at-a-glance dashboard: recent items + active ingest tasks."""

import streamlit as st

from merlin.services import library
from ui.components.task_panel import task_panel


def _count(**filters) -> int:
    return library.list_items(page=1, per_page=1, **filters)["total"]


def render() -> None:
    st.title("🏠 Today")

    m1, m2, m3 = st.columns(3)
    m1.metric("Total items", _count())
    m2.metric("Completed", _count(status="completed"))
    m3.metric("Needs attention", _count(status="failed"))

    left, right = st.columns([3, 2], gap="large")

    with left:
        st.subheader("Recently added")
        recent = library.list_items(page=1, per_page=8)["items"]
        if not recent:
            st.info("Nothing yet — head to **Ingest** to add your first video.")
        for item in recent:
            with st.container(border=True):
                cols = st.columns([1, 3])
                if item.get("thumbnail_url"):
                    cols[0].image(item["thumbnail_url"], width="stretch")
                with cols[1]:
                    st.markdown(f"**{item.get('title') or 'Untitled'}**")
                    sub = item.get("channel") or item.get("author") or ""
                    st.caption(f"{sub} · {(item.get('ingested_at') or '')[:10]}")
                    summary = item.get("summary") or ""
                    if summary:
                        st.caption(summary[:140] + ("…" if len(summary) > 140 else ""))

    with right:
        st.subheader("Ingest tasks")
        task_panel()
