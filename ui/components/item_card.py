"""A compact knowledge-item card for the Library grid."""

import streamlit as st

_STATUS_BADGE = {
    "completed": ("✅", "green"),
    "processing": ("⚙️", "orange"),
    "queued": ("⏳", "gray"),
    "pending": ("⏳", "gray"),
    "failed": ("❌", "red"),
}


def render_item_card(item: dict, key_prefix: str = "lib") -> bool:
    """Render one item. Returns True if the user clicked "Open"."""
    with st.container(border=True):
        if item.get("thumbnail_url"):
            st.image(item["thumbnail_url"], width="stretch")

        title = item.get("title") or "Untitled"
        st.markdown(f"**{title}**")

        meta_bits = []
        if item.get("channel") or item.get("author"):
            meta_bits.append(item.get("channel") or item.get("author"))
        if item.get("duration"):
            meta_bits.append(item["duration"])
        if meta_bits:
            st.caption(" · ".join(str(b) for b in meta_bits))

        icon, color = _STATUS_BADGE.get(item.get("status", ""), ("•", "gray"))
        st.markdown(f":{color}[{icon} {item.get('status', '')}]")

        tags = item.get("tags") or []
        if tags:
            st.caption("🏷 " + ", ".join(tags[:5]))

        summary = item.get("summary")
        if summary:
            snippet = summary[:160] + ("…" if len(summary) > 160 else "")
            st.caption(snippet)

        return st.button("Open", key=f"{key_prefix}_open_{item['id']}", width="stretch")
