"""
UI state helpers — cached resources and session_state initialisation.

Caches the *engine/queue* indirectly (they are module singletons in merlin.*),
and short-lived reference data (tags). Never caches a live DB Session.
"""

from merlin.services import library
import streamlit as st


@st.cache_data(ttl=30)
def cached_tags() -> list[dict]:
    """Tag list with counts, refreshed at most every 30s."""
    return library.list_tags()


@st.cache_data(ttl=60)
def cached_source_types() -> list[dict]:
    """Source types with counts, refreshed at most every 60s."""
    return library.list_source_types()


@st.cache_data(ttl=120)
def cached_ingest_timeline() -> list[dict]:
    return library.ingest_timeline()


@st.cache_data(ttl=120)
def cached_top_channels(limit: int = 12) -> list[dict]:
    return library.top_channels(limit=limit)


@st.cache_data(ttl=120)
def cached_status_counts() -> list[dict]:
    return library.status_counts()


@st.cache_data(ttl=120)
def cached_channel_count() -> int:
    return library.count_channels()


def init_chat_state() -> None:
    if "chat_history" not in st.session_state:
        # list of {"role": "user"|"assistant", "content": str, "citations": [...]}
        st.session_state.chat_history = []


def queue_question(text: str) -> None:
    """Stash a question from the Today omnibox for Chat to auto-submit."""
    st.session_state.pending_question = text


def take_pending_question() -> str | None:
    """Pop a queued question (consumed once on the Chat page)."""
    return st.session_state.pop("pending_question", None)


def clear_caches() -> None:
    """Call after a mutation (ingest/edit/delete) so lists reflect new data."""
    st.cache_data.clear()
