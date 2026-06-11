"""
UI state helpers — cached resources and session_state initialisation.

Caches the *engine/queue* indirectly (they are module singletons in merlin.*),
and short-lived reference data (tags). Never caches a live DB Session.
"""

import streamlit as st

from merlin.services import library


@st.cache_data(ttl=30)
def cached_tags() -> list[dict]:
    """Tag list with counts, refreshed at most every 30s."""
    return library.list_tags()


def init_chat_state() -> None:
    if "chat_history" not in st.session_state:
        # list of {"role": "user"|"assistant", "content": str, "citations": [...]}
        st.session_state.chat_history = []


def clear_caches() -> None:
    """Call after a mutation (ingest/edit/delete) so lists reflect new data."""
    st.cache_data.clear()
