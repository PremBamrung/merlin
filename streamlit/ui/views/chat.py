"""Chat view — streaming RAG chat with inline sources, regenerate & follow-ups."""

import streamlit as st

from merlin.services import chat
from ui.components.citation_list import render_citations
from ui.state import cached_tags, init_chat_state, queue_question, take_pending_question
from ui.util import short

_EXAMPLES = [
    "What have I saved about LLMs?",
    "Summarise the key ideas across my recent videos",
    "What did I learn this week?",
]


def _citation_dicts(chunks) -> list[dict]:
    return [
        {
            "title": c.title,
            "author": c.author,
            "source_type": c.source_type,
            "source_id": c.source_id,
            "excerpt": c.excerpt,
            "knowledge_item_id": c.knowledge_item_id,
        }
        for c in chunks
    ]


def _followups(citations: list[dict]) -> list[str]:
    qs = []
    for c in citations[:2]:
        title = c.get("title")
        if title:
            qs.append(f"Tell me more about “{short(title, 40)}”")
    qs.append("What are the key takeaways?")
    # De-dupe while preserving order.
    seen, out = set(), []
    for q in qs:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out[:3]


def render() -> None:
    st.title("Chat")
    st.caption("Ask your knowledge base")
    init_chat_state()
    history = st.session_state.chat_history

    # --- Toolbar: context filters + clear --------------------------------
    tb1, tb2 = st.columns([6, 1], vertical_alignment="bottom")
    with tb1:
        with st.popover("🔎 Context filters"):
            tag_opts = [t["name"] for t in cached_tags()][:30]
            sel_tags = st.multiselect(
                "Limit to tags", options=tag_opts, key="chat_tags"
            )
    with tb2:
        if st.button("🧹 Clear", width="stretch", disabled=not history):
            st.session_state.chat_history = []
            st.rerun()

    filters = {"tags": sel_tags or None}

    # --- Replay history ---------------------------------------------------
    for idx, msg in enumerate(history):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("citations"):
                render_citations(msg["citations"], key_prefix=f"m{idx}")

    # --- Resolve the prompt (typed > omnibox/chip/regenerate) -------------
    pending = take_pending_question()
    typed = st.chat_input("Ask your knowledge base…")
    prompt = typed or pending

    if not prompt:
        if not history:
            _empty_state()
        else:
            _post_answer_actions(history)
        return

    # --- Handle a new prompt ---------------------------------------------
    history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    llm_history = [{"role": m["role"], "content": m["content"]} for m in history[:-1]]

    with st.chat_message("assistant"):
        try:
            gen, chunks = chat.answer(prompt, llm_history, filters)
            full = st.write_stream(gen)
            render_citations(chunks, key_prefix="live")
            citations = _citation_dicts(chunks)
        except Exception as exc:  # surface LLM/config errors in-line
            full = f"⚠️ {exc}"
            citations = []
            st.error(full)

    history.append({"role": "assistant", "content": full, "citations": citations})
    st.rerun()  # re-render from history so the action bar shows under the answer


def _empty_state() -> None:
    st.caption("Try asking")
    cols = st.columns(len(_EXAMPLES))
    for col, example in zip(cols, _EXAMPLES, strict=False):
        with col:
            if st.button(example, width="stretch", key=f"ex_{example}"):
                queue_question(example)
                st.rerun()


def _post_answer_actions(history: list[dict]) -> None:
    last = history[-1]
    if last["role"] != "assistant":
        return

    a1, a2, _ = st.columns([1, 1, 4])
    with a1:
        with st.popover("📋 Copy"):
            st.code(last["content"], language="markdown")
    with a2:
        if st.button("🔁 Regenerate"):
            # Drop the last assistant + its user turn, re-ask the same question.
            history.pop()  # assistant
            if history and history[-1]["role"] == "user":
                queue_question(history.pop()["content"])
            st.rerun()

    followups = _followups(last.get("citations") or [])
    if followups:
        st.caption("Follow up")
        cols = st.columns(len(followups))
        for col, q in zip(cols, followups, strict=False):
            with col:
                if st.button(q, width="stretch", key=f"fu_{q}"):
                    queue_question(q)
                    st.rerun()
