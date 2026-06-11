"""Render chat citations (RetrievedChunk list or stored dicts)."""

import streamlit as st


def _field(c, name):
    return getattr(c, name, None) if not isinstance(c, dict) else c.get(name)


def render_citations(chunks) -> None:
    if not chunks:
        return
    with st.expander(f"📚 {len(chunks)} source(s)"):
        for i, c in enumerate(chunks, 1):
            title = _field(c, "title") or "Untitled"
            author = _field(c, "author")
            source_type = (_field(c, "source_type") or "").upper()
            line = f"**[{i}]** {title}"
            if author:
                line += f" — *{author}*"
            if source_type:
                line += f"  `{source_type}`"
            st.markdown(line)
