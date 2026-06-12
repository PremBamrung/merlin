"""Library view — browse, search, filter, sort, and inspect knowledge items.

When `?item=<id>` is present, delegates to the full-width Reader view; otherwise
renders the toolbar + grid/list of cards.
"""

from math import ceil

import streamlit as st

from merlin.services import library
from ui.components.item_card import item_card, item_row
from ui.state import cached_source_types, cached_tags
from ui.views import reader

_PER_PAGE = 12  # divisible by 2/3/4 (the density options)
_DENSITY = {"Comfortable": 2, "Cozy": 3, "Compact": 4}
_SORTS = {
    "Newest": "newest",
    "Oldest": "oldest",
    "Longest": "longest",
    "Title A–Z": "title",
}


def render() -> None:
    # Reader takes over the page when an item is selected (query param keeps
    # the URL shareable; session_state survives in-app navigation).
    item_id = st.query_params.get("item") or st.session_state.get("open_item")
    if item_id:
        reader.render(item_id)
        return

    st.title("Library")

    # --- Toolbar: search · sort · view · density --------------------------
    t1, t2, t3, t4 = st.columns([4, 2, 2, 2], vertical_alignment="bottom")
    with t1:
        search = st.text_input(
            "Search",
            placeholder="Full-text search across titles & summaries…",
            key="lib_search",
        )
    with t2:
        sort_label = st.selectbox("Sort", list(_SORTS), key="lib_sort")
    with t3:
        view = st.segmented_control(
            "View", ["Grid", "List"], default="Grid", key="lib_view"
        )
    with t4:
        density = st.segmented_control(
            "Density", list(_DENSITY), default="Cozy", key="lib_density"
        )

    # --- Filter chips: source type + tags ---------------------------------
    sources = cached_source_types()
    sel_source = None
    if len(sources) > 1:
        opts = ["Everything"] + [s["name"] for s in sources]
        labels = {s["name"]: f"{s['name'].title()} ({s['count']})" for s in sources}
        labels["Everything"] = "Everything"
        chosen = st.segmented_control(
            "Source",
            opts,
            default="Everything",
            format_func=lambda o: labels.get(o, o),
            key="lib_source",
            label_visibility="collapsed",
        )
        sel_source = None if chosen in (None, "Everything") else chosen

    tag_opts = [t["name"] for t in cached_tags()][:20]
    sel_tags = (
        st.pills("Filter by tag", tag_opts, selection_mode="multi", key="lib_tags")
        if tag_opts
        else []
    )

    filters = {
        "search": search or None,
        "tags": sel_tags or None,
        "source_type": sel_source,
        "sort": _SORTS[sort_label],
    }

    # Reset the pager whenever the filter/sort set changes.
    sig = repr(filters)
    if st.session_state.get("lib_filter_sig") != sig:
        st.session_state["lib_filter_sig"] = sig
        st.session_state.pop("lib_page", None)

    # --- Fetch + paginate -------------------------------------------------
    probe = library.list_items(page=1, per_page=_PER_PAGE, **filters)
    total = probe["total"]
    num_pages = max(1, ceil(total / _PER_PAGE))

    if st.session_state.get("lib_page", 1) > num_pages:
        st.session_state.pop("lib_page", None)

    st.caption(f"{total:,} item(s)")
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

    # --- Render -----------------------------------------------------------
    if view == "List":
        for item in items:
            item_row(item)
    else:
        ncols = _DENSITY.get(density, 3)
        for start in range(0, len(items), ncols):
            row = items[start : start + ncols]
            cols = st.columns(ncols)
            for col, item in zip(cols, row, strict=False):
                with col:
                    item_card(item)
