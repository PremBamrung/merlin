"""Inline source cards for chat answers — native widgets.

Accepts either live `RetrievedChunk` objects or the stored citation dicts kept
in chat history.
"""

import streamlit as st
from ui.util import short, youtube_url


def _field(c, name):
    return getattr(c, name, None) if not isinstance(c, dict) else c.get(name)


def render_citations(chunks, key_prefix: str = "c") -> None:
    if not chunks:
        return
    st.caption(f"{len(chunks)} source(s)")
    for i, c in enumerate(chunks):
        title = _field(c, "title") or "Untitled"
        author = _field(c, "author")
        stype = (_field(c, "source_type") or "").upper()
        source_id = _field(c, "source_id")
        excerpt = _field(c, "excerpt")

        with st.container(border=True):
            head = f"**{title}**"
            if stype:
                head = f"`{stype}` {head}"
            st.markdown(head)
            if author:
                st.caption(author)
            if excerpt:
                st.caption(short(excerpt, 220))
            if stype == "YOUTUBE" and source_id:
                st.link_button(
                    "YouTube ↗", youtube_url(source_id), key=f"{key_prefix}_{i}"
                )
