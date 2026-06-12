"""Knowledge-item cards — built from native Streamlit widgets.

A card is a bordered container with a thumbnail image, a title button (opens the
Reader in-session), a caption meta line, and tag badges. No custom HTML/CSS.
"""

import streamlit as st

from ui.styles import STATUS_EMOJI
from ui.util import rel_date, short


def _open(item_id: str) -> None:
    from ui import nav  # lazy: avoid views→item_card→nav cycle

    nav.open_reader(item_id)


def _meta_caption(item: dict, with_duration: bool = False) -> str:
    bits = []
    sub = item.get("channel") or item.get("author")
    if sub:
        bits.append(short(sub, 30))
    if with_duration and item.get("duration"):
        bits.append(item["duration"])
    if item.get("ingested_at"):
        bits.append(rel_date(item["ingested_at"]))
    emoji = STATUS_EMOJI.get(item.get("status", ""), "")
    line = " · ".join(bits)
    return f"{emoji} {line}" if emoji else line


def _tags_caption(item: dict, limit: int = 4) -> str:
    tags = item.get("tags") or []
    if not tags:
        return ""
    shown = " ".join(f"`{t}`" for t in tags[:limit])
    if len(tags) > limit:
        shown += f" +{len(tags) - limit}"
    return shown


def item_card(item: dict) -> None:
    """Grid card."""
    with st.container(border=True):
        if item.get("thumbnail_url"):
            st.image(item["thumbnail_url"], use_container_width=True)
        if item.get("duration"):
            st.caption(f"⏱ {item['duration']}")
        st.button(
            item.get("title") or "Untitled",
            key=f"card_{item['id']}",
            type="tertiary",
            use_container_width=True,
            on_click=_open,
            args=(item["id"],),
        )
        st.caption(_meta_caption(item))
        summary = item.get("summary")
        if summary:
            st.caption(short(summary, 130))
        tags = _tags_caption(item)
        if tags:
            st.caption(tags)


def item_row(item: dict) -> None:
    """List row."""
    with st.container(border=True):
        c1, c2 = st.columns([1, 4], vertical_alignment="center")
        with c1:
            if item.get("thumbnail_url"):
                st.image(item["thumbnail_url"], use_container_width=True)
        with c2:
            st.button(
                item.get("title") or "Untitled",
                key=f"row_{item['id']}",
                type="tertiary",
                use_container_width=True,
                on_click=_open,
                args=(item["id"],),
            )
            st.caption(_meta_caption(item, with_duration=True))
            tags = _tags_caption(item, limit=8)
            if tags:
                st.caption(tags)
