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
