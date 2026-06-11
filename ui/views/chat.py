"""Chat view — streaming RAG chat over the knowledge base."""

import streamlit as st

from merlin.services import chat
from ui.components.citation_list import render_citations
from ui.state import cached_tags, init_chat_state


def _citation_dicts(chunks) -> list[dict]:
    return [
        {
            "title": c.title,
            "author": c.author,
            "source_type": c.source_type,
            "id": c.knowledge_item_id,
        }
        for c in chunks
    ]


def render() -> None:
    st.title("💬 Chat")
    init_chat_state()

    fcol, ccol = st.columns([4, 1])
    with fcol:
        with st.popover("🔎 Context filters"):
            tag_opts = [t["name"] for t in cached_tags()]
            sel_tags = st.multiselect(
                "Limit to tags", options=tag_opts, key="chat_tags"
            )
    with ccol:
        if st.button("🧹 Clear", width="stretch"):
            st.session_state.chat_history = []
            st.rerun()

    filters = {"tags": sel_tags or None}

    # Replay history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("citations"):
                render_citations(msg["citations"])

    prompt = st.chat_input("Ask your knowledge base…")
    if not prompt:
        return

    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Clean history (role/content only) for the LLM — exclude the new prompt
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.chat_history[:-1]
    ]

    with st.chat_message("assistant"):
        try:
            gen, chunks = chat.answer(prompt, history, filters)
            full = st.write_stream(gen)
            render_citations(chunks)
            citations = _citation_dicts(chunks)
        except Exception as exc:  # surface LLM/config errors in-line
            full = f"⚠️ {exc}"
            citations = []
            st.error(full)

    st.session_state.chat_history.append(
        {"role": "assistant", "content": full, "citations": citations}
    )
