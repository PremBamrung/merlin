"""Insights — charts over the whole knowledge base."""

import streamlit as st

from ui.charts import activity_heatmap, hbar, monthly_bar, status_donut
from ui.state import (
    cached_channel_count,
    cached_ingest_timeline,
    cached_status_counts,
    cached_tags,
    cached_top_channels,
)
from ui.styles import TAG_SWATCHES


def render() -> None:
    st.session_state["_page"] = "insights"
    st.title("Insights")
    st.caption("How your library has grown")

    timeline = cached_ingest_timeline()
    total = sum(d["count"] for d in timeline)
    if not total:
        st.info("No items yet — ingest some videos to see insights.")
        return

    # --- Headline metrics -------------------------------------------------
    busiest = max((d["count"] for d in timeline), default=0)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total items", f"{total:,}")
    c2.metric("Distinct channels", f"{cached_channel_count():,}")
    c3.metric("Most in a day", f"{busiest:,}")

    st.divider()

    # --- Activity heatmap -------------------------------------------------
    st.subheader("Ingest activity")
    fig = activity_heatmap(timeline)
    if fig:
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Channels + monthly -----------------------------------------------
    left, right = st.columns(2)
    with left:
        st.subheader("Top channels")
        fig = hbar(cached_top_channels(limit=12))
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("Items per month")
        fig = monthly_bar(timeline)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Status + tags ----------------------------------------------------
    left2, right2 = st.columns(2)
    with left2:
        st.subheader("Status")
        fig = status_donut(cached_status_counts())
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    with right2:
        tags = cached_tags()
        if tags:
            st.subheader("Top tags")
            fig = hbar(tags[:12], color=TAG_SWATCHES[3])
            if fig:
                st.plotly_chart(fig, use_container_width=True)
