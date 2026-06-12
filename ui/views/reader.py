"""Reader view — full-width reading surface for a single knowledge item.

Reached from the Library grid via the `?item=<id>` query param (the cards link
here). Replaces the old cramped detail dialog: the summary finally gets room,
topics become timestamped YouTube deep-links, and item actions live here.
"""

import streamlit as st

from merlin.services import ingest, library
from ui.state import clear_caches
from ui.util import ts_to_seconds, youtube_url

_LENGTHS = ["short", "medium", "long"]


def _close() -> None:
    st.query_params.pop("item", None)
    st.session_state.pop("open_item", None)


def _meta_line(item: dict) -> str:
    bits = [
        item.get("channel") or item.get("author"),
        item.get("duration"),
        (item.get("detected_language") or "").upper() or None,
        f"{item['word_count']:,} words" if item.get("word_count") else None,
        (item.get("ingested_at") or "")[:10] or None,
    ]
    return " · ".join(str(b) for b in bits if b)


def render(item_id: str) -> None:
    item = library.get_item(item_id)
    if not item:
        st.warning("This item no longer exists.")
        if st.button("← Back to Library"):
            _close()
            st.rerun()
        return

    # --- Top bar: back + open-on-source ------------------------------------
    top_l, top_r = st.columns([3, 2], vertical_alignment="center")
    with top_l:
        if st.button("← Library", key="reader_back"):
            _close()
            st.rerun()
    with top_r:
        if item.get("source_type") == "youtube" and item.get("source_id"):
            st.link_button(
                "↗ Open on YouTube",
                youtube_url(item["source_id"]),
                width="stretch",
            )

    # --- Title + meta ------------------------------------------------------
    st.title(item.get("title") or "Untitled")
    st.caption(_meta_line(item))
    tags = item.get("tags") or []
    if tags:
        st.caption(" ".join(f"`{t}`" for t in tags))

    if item.get("status") == "failed" and item.get("error_message"):
        st.error(item["error_message"])

    st.divider()

    # --- Summary -----------------------------------------------------------
    if item.get("summary"):
        st.markdown(item["summary"])
    elif item.get("status") in ("processing", "queued", "pending"):
        st.info("Summary is still being generated — check back shortly.")
    else:
        st.info("No summary yet. Try re-summarising below.")

    # --- Topics & timestamps (deep links) ----------------------------------
    topics = item.get("topics") or {}
    if not topics and item.get("timestamps"):
        topics = item["timestamps"]
    if topics and item.get("source_id"):
        with st.expander(f"🕑 Topics & timestamps ({len(topics)})", expanded=False):
            for topic, stamp in topics.items():
                secs = ts_to_seconds(str(stamp))
                if secs is not None:
                    link = youtube_url(item["source_id"], secs)
                    st.markdown(f"- [`{stamp}`]({link}) — {topic}")
                else:
                    st.markdown(f"- {topic}")

    st.divider()

    # --- Actions -----------------------------------------------------------
    _actions(item)


def _actions(item: dict) -> None:
    item_id = item["id"]
    summary = item.get("summary") or ""

    a1, a2, a3 = st.columns(3)

    # Copy (native copy button on st.code) + export.
    with a1:
        with st.popover("📋 Copy", width="stretch"):
            st.caption("Markdown — use the copy icon:")
            st.code(_as_markdown(item), language="markdown")
    with a2:
        st.download_button(
            "⬇ Export .md",
            data=_as_markdown(item),
            file_name=f"{_slug(item.get('title'))}.md",
            mime="text/markdown",
            width="stretch",
            disabled=not summary,
        )
    with a3:
        with st.popover("🗑 Delete", width="stretch"):
            st.warning("Delete this item permanently?")
            if st.button("Yes, delete", type="primary", key="reader_del"):
                library.delete_item(item_id)
                clear_caches()
                _close()
                st.rerun()

    st.write("")

    # Re-summarise with a chosen length.
    with st.container(border=True):
        rc1, rc2 = st.columns([3, 1], vertical_alignment="bottom")
        with rc1:
            length = st.segmented_control(
                "Summary length",
                options=_LENGTHS,
                default=item.get("summary_length")
                if item.get("summary_length") in _LENGTHS
                else "short",
                key="reader_len",
            )
        with rc2:
            if st.button("🔁 Re-summarise", width="stretch", key="reader_retry"):
                try:
                    ingest.retry(item_id, summary_length=length or "short")
                    st.toast("Re-ingest queued — progress on Today / Ingest.")
                except ValueError as exc:
                    st.error(str(exc))

    # Edit tags.
    with st.container(border=True):
        current = ", ".join(item.get("tags") or [])
        new_tags = st.text_input(
            "Tags (comma-separated)", value=current, key="reader_tags"
        )
        if st.button("💾 Save tags", key="reader_save_tags"):
            parsed = [t.strip() for t in new_tags.split(",") if t.strip()]
            library.update_item(item_id, tags=parsed)
            clear_caches()
            st.toast("Tags saved")
            st.rerun()


def _as_markdown(item: dict) -> str:
    lines = [f"# {item.get('title') or 'Untitled'}", ""]
    sub = item.get("channel") or item.get("author")
    if sub:
        lines.append(f"**Source:** {sub}")
    if item.get("source_type") == "youtube" and item.get("source_id"):
        lines.append(f"**URL:** {youtube_url(item['source_id'])}")
    tags = item.get("tags") or []
    if tags:
        lines.append(f"**Tags:** {', '.join(tags)}")
    lines += ["", item.get("summary") or "_No summary._"]
    return "\n".join(lines)


def _slug(title: str | None) -> str:
    base = (title or "merlin-item").lower()
    return "".join(c if c.isalnum() else "-" for c in base).strip("-")[:60] or "item"
