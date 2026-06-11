"""Library view — browse, search, filter, and inspect knowledge items."""

from math import ceil

import streamlit as st

from merlin.services import ingest, library
from ui.components.item_card import render_item_card
from ui.state import cached_tags, clear_caches

_PER_PAGE = 12
_STATUSES = ["completed", "processing", "queued", "pending", "failed"]


def _clear_detail() -> None:
    st.session_state.detail_id = None


@st.dialog("Item detail", width="large", on_dismiss=_clear_detail)
def _detail_dialog(item_id: str) -> None:
    item = library.get_item(item_id)
    if not item:
        st.warning("Item no longer exists.")
        return

    st.markdown(f"### {item.get('title') or 'Untitled'}")
    meta = [
        item.get("channel") or item.get("author"),
        item.get("duration"),
        item.get("detected_language"),
    ]
    st.caption(" · ".join(str(m) for m in meta if m))

    if item.get("status") == "failed" and item.get("error_message"):
        st.error(item["error_message"])

    if item.get("summary"):
        st.markdown(item["summary"])
    else:
        st.info("No summary yet.")

    topics = item.get("topics") or {}
    if topics:
        with st.expander("Topics & timestamps"):
            for topic, ts in topics.items():
                st.markdown(f"- **{topic}** — `{ts}`")

    # Editable tags
    current_tags = ", ".join(item.get("tags") or [])
    new_tags = st.text_input("Tags (comma-separated)", value=current_tags)

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("💾 Save tags", width="stretch"):
            parsed = [t.strip() for t in new_tags.split(",") if t.strip()]
            library.update_item(item_id, tags=parsed)
            clear_caches()
            st.toast("Tags saved")
            st.rerun()
    with c2:
        if st.button("🔁 Re-summarise", width="stretch"):
            try:
                ingest.retry(item_id)
                st.toast("Re-ingest queued")
            except ValueError as exc:
                st.error(str(exc))
    with c3:
        if st.button("🗑 Delete", width="stretch"):
            library.delete_item(item_id)
            clear_caches()
            _clear_detail()
            st.rerun()


def render() -> None:
    st.title("📚 Library")

    if "detail_id" not in st.session_state:
        st.session_state.detail_id = None

    # --- Filters ---
    fcol1, fcol2, fcol3 = st.columns([3, 2, 2])
    with fcol1:
        search = st.text_input(
            "Search", placeholder="Full-text search…", key="lib_search"
        )
    with fcol2:
        tag_opts = [t["name"] for t in cached_tags()]
        sel_tags = st.multiselect("Tags", options=tag_opts, key="lib_tags")
    with fcol3:
        status = st.selectbox("Status", options=["all", *_STATUSES], key="lib_status")

    filters = {
        "search": search or None,
        "tags": sel_tags or None,
        "status": None if status == "all" else status,
    }

    # Reset the pager when the filter set changes (delete the widget key —
    # the supported, warning-free way to reset a widget's value).
    sig = repr(filters)
    if st.session_state.get("lib_filter_sig") != sig:
        st.session_state["lib_filter_sig"] = sig
        st.session_state.pop("lib_page", None)

    # --- Fetch + paginate ---
    probe = library.list_items(page=1, per_page=_PER_PAGE, **filters)
    total = probe["total"]
    num_pages = max(1, ceil(total / _PER_PAGE))

    # If a stored page now exceeds the range (e.g. after a delete), reset it.
    if st.session_state.get("lib_page", 1) > num_pages:
        st.session_state.pop("lib_page", None)

    st.caption(f"{total} item(s)")
    page = st.pagination(num_pages, key="lib_page") if num_pages > 1 else 1
    data = (
        probe
        if page == 1
        else library.list_items(page=page, per_page=_PER_PAGE, **filters)
    )

    items = data["items"]
    if not items:
        st.info("No items match these filters.")
        return

    # --- Grid (3 columns) ---
    cols = st.columns(3)
    for idx, item in enumerate(items):
        with cols[idx % 3]:
            if render_item_card(item):
                st.session_state.detail_id = item["id"]
                st.rerun()

    if st.session_state.detail_id:
        _detail_dialog(st.session_state.detail_id)
