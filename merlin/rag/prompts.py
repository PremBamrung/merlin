MERLIN_SYSTEM_PROMPT = """You are Merlin, a personal knowledge assistant.
You have access to the user's curated knowledge base which includes YouTube video summaries, articles, and other content they have saved.

When answering questions:
1. Base your answers primarily on the provided context from the knowledge base
2. Cite specific sources using [Source: Title] notation when referencing them
3. If the context doesn't contain relevant information, say so clearly and answer from general knowledge if appropriate
4. Be concise but thorough
5. Use markdown formatting for clarity

Context from knowledge base:
{context}
"""


def format_context(chunks) -> str:
    if not chunks:
        return "No relevant items found in the knowledge base."
    parts = []
    for i, chunk in enumerate(chunks, 1):
        source_label = f"{chunk.source_type.upper()}: {chunk.title}"
        if chunk.author:
            source_label += f" (by {chunk.author})"
        parts.append(f"[{i}] {source_label}\n{chunk.excerpt}")
    return "\n\n---\n\n".join(parts)


# --------------------------------------------------------------------------- #
# Single-item chat — talk to ONE item using its full transcript, not RAG.
# --------------------------------------------------------------------------- #

ITEM_CHAT_SYSTEM_PROMPT = """You are Merlin, a personal knowledge assistant. \
The user is reading one specific item and wants to discuss it with you.

Answer strictly from the item below — its transcript is the ground truth; the \
summary is a generated overview for orientation. When the transcript and the \
summary disagree, trust the transcript. If the item doesn't cover something the \
user asks, say so plainly rather than inventing an answer.

Guidelines:
1. Be concise but substantive; quote or paraphrase the transcript when useful.
2. Do NOT cite timestamps or claim a specific point in the video — this \
transcript has no reliable time markers, so any timestamp would be fabricated.
3. Use markdown for clarity.

{context}
"""

# Cap the transcript so an unusually long video can't blow the context window.
# Generous on purpose — most transcripts are well under this.
_TRANSCRIPT_CHAR_CAP = 120_000


def format_item_context(item: dict) -> str:
    """Lay out a single item (metadata + summary + full transcript) for chat.

    `item` is the dict from `library.get_item` (includes `raw_content`).
    """
    meta_bits = [
        f"{item.get('source_type', 'item').upper()}",
        item.get("channel") or item.get("author"),
        item.get("detected_language"),
    ]
    meta_line = " · ".join(str(b) for b in meta_bits if b)

    parts = [
        f"TITLE: {item.get('title') or 'Untitled'}",
        f"SOURCE: {meta_line}" if meta_line else None,
    ]

    if item.get("summary"):
        parts.append(f"\nSUMMARY:\n{item['summary']}")

    transcript = (item.get("raw_content") or "").strip()
    if transcript:
        if len(transcript) > _TRANSCRIPT_CHAR_CAP:
            transcript = (
                transcript[:_TRANSCRIPT_CHAR_CAP] + "\n\n[transcript truncated]"
            )
        parts.append(f"\nFULL TRANSCRIPT:\n{transcript}")
    elif not item.get("summary"):
        parts.append("\n(No transcript or summary is available for this item.)")

    return "\n".join(p for p in parts if p)
