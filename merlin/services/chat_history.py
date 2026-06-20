"""Chat-history service — persistence for continuable library-wide chats.

The React `/chat` tab saves each turn here so a thread can be reopened and kept
going with full context. A turn is stored as its **Vercel AI SDK `UIMessage`
parts** (JSON in `chat_messages.parts`) — text, reasoning, tool calls/results,
and our citation data-parts — so a reopened thread renders exactly as it did
live and replays cleanly as agent history (the adapter's `load_messages` skips
the custom data-parts and reconstructs tool-call/result pairs).

Persistence is **client-driven**: the browser PUTs the full message list at the
end of each turn (it holds the exact rendered parts, citations included), and
`save_thread` upserts the thread + replaces its messages. Titles are generated
here, lazily, on the first turn — by then the answer has already streamed, so
the (cheap) LLM call blocks nothing the user is waiting on.

Framework-agnostic: returns plain dicts, opens short-lived sessions, never holds
a `Session`. The Reader per-item chat is ephemeral and never calls this module.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging

from sqlalchemy import select

from merlin.db.engine import get_db
from merlin.db.models import ChatMessage, ChatThread

logger = logging.getLogger(__name__)

__all__ = [
    "save_thread",
    "list_threads",
    "get_thread",
    "rename_thread",
    "delete_thread",
    "generate_title",
]

# Cap the preview/title source so a pathologically long first message can't bloat
# the title prompt or the sidebar preview.
_PREVIEW_CHARS = 140
_TITLE_INPUT_CHARS = 2000


def _first_user_text(messages: list[dict]) -> str:
    """Concatenated text of the first user message's text parts (for title/preview)."""
    for msg in messages:
        if msg.get("role") != "user":
            continue
        texts = [
            p.get("text", "")
            for p in (msg.get("parts") or [])
            if isinstance(p, dict) and p.get("type") == "text"
        ]
        joined = " ".join(t for t in texts if t).strip()
        if joined:
            return joined
    return ""


def generate_title(first_message: str) -> str | None:
    """One cheap LLM call naming a conversation; None on any failure.

    Best-effort: a missing key, a model error, or an empty reply all fall back to
    None (the caller leaves the title NULL and the UI shows a preview instead).
    """
    text = (first_message or "").strip()
    if not text:
        return None
    try:
        from merlin.rag.agent import title_agent
        from merlin.rag.model import build_chat_model

        result = title_agent.run_sync(
            text[:_TITLE_INPUT_CHARS], model=build_chat_model()
        )
        title = (result.output or "").strip().strip('"').strip()
        # Models sometimes still emit a trailing period or a "Title:" lead-in.
        title = title.removeprefix("Title:").strip().rstrip(".").strip()
        return title[:512] or None
    except Exception as exc:  # never let title generation break a save
        logger.warning("chat title generation failed: %s", exc)
        return None


def save_thread(
    thread_id: str,
    messages: list[dict],
    title: str | None = None,
) -> dict:
    """Upsert a thread and replace its messages with `messages` (idempotent).

    `messages` is the full ordered list of `{id?, role, parts}` from the client.
    Creates the thread row lazily on first save (so no empty threads exist). On
    the first save with no stored title, generates one from the first user
    message. Returns `{"id", "title"}`.
    """
    # Generate the title BEFORE opening the DB session — the LLM call can take a
    # second or two and we don't want to hold a write transaction open for it.
    new_title: str | None = None
    with get_db() as db:
        thread = db.get(ChatThread, thread_id)
        needs_title = title is None and (thread is None or not thread.title)
    if title is not None:
        new_title = title
    elif needs_title:
        new_title = generate_title(_first_user_text(messages))

    with get_db() as db:
        thread = db.get(ChatThread, thread_id)
        if thread is None:
            thread = ChatThread(id=thread_id)
            db.add(thread)
        if new_title:
            thread.title = new_title

        # Replace the message set wholesale — the client always sends the full
        # list, so this is simpler and race-free for a single user than diffing.
        # PKs are freshly generated (not the client message id) so reusing an id
        # across threads can never collide; the client id isn't needed once the
        # parts are stored.
        db.query(ChatMessage).filter(ChatMessage.thread_id == thread_id).delete()
        for seq, msg in enumerate(messages):
            db.add(
                ChatMessage(
                    thread_id=thread_id,
                    seq=seq,
                    role=msg.get("role") or "assistant",
                    parts=json.dumps(msg.get("parts") or []),
                )
            )
        # Bump updated_at even though only children changed (sidebar ordering).
        thread.updated_at = datetime.now(UTC)
        db.flush()
        result = {"id": thread.id, "title": thread.title}
    return result


def list_threads() -> list[dict]:
    """All threads newest-first: `{id, title, created_at, updated_at,
    message_count, preview}`. `preview` is the first user message, for titleless
    rows."""
    with get_db() as db:
        threads = (
            db.execute(select(ChatThread).order_by(ChatThread.updated_at.desc()))
            .scalars()
            .all()
        )
        out = []
        for t in threads:
            msgs = t.messages  # eager-ordered by seq via the relationship
            preview = ""
            for m in msgs:
                if m.role == "user":
                    parts = json.loads(m.parts or "[]")
                    preview = " ".join(
                        p.get("text", "")
                        for p in parts
                        if isinstance(p, dict) and p.get("type") == "text"
                    ).strip()
                    if preview:
                        break
            out.append(
                {
                    "id": t.id,
                    "title": t.title,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                    "message_count": len(msgs),
                    "preview": preview[:_PREVIEW_CHARS] or None,
                }
            )
        return out


def get_thread(thread_id: str) -> dict | None:
    """One thread with its ordered messages (parts parsed back to JSON), or None."""
    with get_db() as db:
        thread = db.get(ChatThread, thread_id)
        if thread is None:
            return None
        return {
            "id": thread.id,
            "title": thread.title,
            "created_at": thread.created_at.isoformat() if thread.created_at else None,
            "updated_at": thread.updated_at.isoformat() if thread.updated_at else None,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "parts": json.loads(m.parts or "[]"),
                }
                for m in thread.messages
            ],
        }


def rename_thread(thread_id: str, title: str) -> bool:
    """Set a thread's title; False if the thread doesn't exist."""
    with get_db() as db:
        thread = db.get(ChatThread, thread_id)
        if thread is None:
            return False
        thread.title = (title or "").strip()[:512] or None
        return True


def delete_thread(thread_id: str) -> bool:
    """Delete a thread (and its messages, via cascade); False if missing."""
    with get_db() as db:
        thread = db.get(ChatThread, thread_id)
        if thread is None:
            return False
        db.delete(thread)
        return True
