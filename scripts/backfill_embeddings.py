"""Backfill semantic-search vectors for already-ingested library items.

Embeds every completed item that has no stored vector yet (one vector per item,
built from title + tags + summary — the same text the ingest hook embeds) and
writes it to the `embeddings` table. New items are embedded automatically at
ingest time; this is the one-off pass for the existing corpus.

Requires a configured embedding provider. With `EMBEDDING_PROVIDER=none` it does
nothing. The engine binds to `settings.database_url` at import, so point it at
the real DB with the env var (matching the rest of the project) rather than a
flag:

    DATABASE_URL="sqlite:///$(pwd)/data/merlin.db" \\
        uv run python scripts/backfill_embeddings.py

    # preview what would be embedded, no API calls, no writes:
    DATABASE_URL="sqlite:///$(pwd)/data/merlin.db" \\
        uv run python scripts/backfill_embeddings.py --dry-run

Rate limits: a free Jina key is ~100 RPM / 100K TPM. The full corpus is only a
dozen-odd batched requests (RPM is never a concern), but firing ~200K tokens in
under a minute can trip the free-tier TPM cap. Two safeguards: batches retry on
429/5xx with backoff (--max-retries), and --sleep paces them. On a free key,
`--sleep 12` keeps each batch under the 100K-token/min window; a paid key
(2M TPM) needs neither. The run is resumable — it skips already-embedded items.

Options:
    --batch N         texts per Jina embeddings call (default 64)
    --limit N         stop after N items (default: all)
    --sleep S         seconds to pause between batches (default 0)
    --max-retries N   retries per batch on 429/5xx with backoff (default 5)
    --dry-run         report the work and exit without calling Jina or writing
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import requests

# Running a script puts scripts/ (not the repo root) on sys.path; add the root
# so `import merlin` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from merlin.db.engine import SessionFactory  # noqa: E402
from merlin.db.models import KnowledgeItem  # noqa: E402
from merlin.db.repositories.knowledge import EmbeddingRepository  # noqa: E402
from merlin.rag.embeddings import get_embedder, item_embed_text  # noqa: E402

# HTTP statuses worth retrying: 429 (rate limit) + transient 5xx.
_RETRYABLE = {429, 500, 502, 503, 504}


def _embed_with_retry(
    embedder, texts: list[str], max_retries: int
) -> list[list[float]]:
    """Embed a batch, backing off on rate-limit/5xx errors.

    The interactive retriever fails fast to FTS5 on any Jina error (a chat query
    must not hang); the *backfill* is the opposite — it should wait out a 429 so
    a long run survives a low free-tier TPM cap (100K/min). Honours `Retry-After`
    when present, else exponential backoff capped at 60s.
    """
    delay = 5.0
    for attempt in range(max_retries + 1):
        try:
            return embedder.embed(texts, query=False)
        except requests.HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            if status not in _RETRYABLE or attempt == max_retries:
                raise
            retry_after = exc.response.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else delay
            print(
                f"  rate-limited/transient ({status}); retrying in {wait:.0f}s "
                f"(attempt {attempt + 1}/{max_retries})"
            )
            time.sleep(wait)
            delay = min(delay * 2, 60.0)
    raise RuntimeError("unreachable")  # loop always returns or raises


def _pending_items(session, limit: int | None) -> list[dict]:
    """Completed items that have no vector yet, as plain dicts."""
    done = EmbeddingRepository.item_ids_with_embeddings(session)
    q = (
        session.query(
            KnowledgeItem.id,
            KnowledgeItem.title,
            KnowledgeItem.summary,
            KnowledgeItem.tags,
        )
        .filter(KnowledgeItem.status == "completed")
        .order_by(KnowledgeItem.ingested_at)
    )
    items: list[dict] = []
    for row in q.all():
        if row[0] in done:
            continue
        try:
            tags = json.loads(row[3]) if row[3] else []
        except (ValueError, TypeError):
            tags = []
        text = item_embed_text(row[1], row[2], tags)
        if not text:
            continue  # nothing embeddable (no title/summary/tags)
        items.append({"id": row[0], "title": row[1], "text": text})
        if limit and len(items) >= limit:
            break
    return items


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--batch", type=int, default=64, help="texts per Jina call")
    ap.add_argument("--limit", type=int, default=None, help="max items to embed")
    ap.add_argument("--sleep", type=float, default=0.0, help="pause between batches")
    ap.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="retries per batch on 429/5xx with backoff (default 5)",
    )
    ap.add_argument("--dry-run", action="store_true", help="report only; no calls")
    args = ap.parse_args()

    embedder = get_embedder()
    if not embedder.enabled:
        raise SystemExit(
            "No embedding provider configured (EMBEDDING_PROVIDER=none). "
            "Set EMBEDDING_PROVIDER=jina and JINA_API_KEY to backfill."
        )

    with SessionFactory() as session:
        pending = _pending_items(session, args.limit)

    if not pending:
        print("Nothing to backfill — all completed items already have vectors.")
        return

    print(
        f"{len(pending)} item(s) to embed with {embedder.model} (batch={args.batch})."
    )
    if args.dry_run:
        for it in pending[:10]:
            print(f"  - {it['id']}  {it['title'][:70]!r}")
        if len(pending) > 10:
            print(f"  … and {len(pending) - 10} more")
        print("Dry run — no API calls made, nothing written.")
        return

    done = 0
    for start in range(0, len(pending), args.batch):
        batch = pending[start : start + args.batch]
        vectors = _embed_with_retry(
            embedder, [it["text"] for it in batch], args.max_retries
        )
        if len(vectors) != len(batch):
            raise SystemExit(
                f"Jina returned {len(vectors)} vectors for {len(batch)} inputs — "
                "aborting before writing a misaligned batch."
            )
        with SessionFactory() as session:
            for it, vec in zip(batch, vectors, strict=True):
                EmbeddingRepository.upsert(
                    session,
                    knowledge_item_id=it["id"],
                    chunk_index=0,
                    chunk_text=it["text"],
                    embedding=json.dumps(vec),
                    embedding_model=embedder.model,
                )
            session.commit()
        done += len(batch)
        print(f"  embedded {done}/{len(pending)}")
        if args.sleep and start + args.batch < len(pending):
            time.sleep(args.sleep)

    print(f"Done — {done} item(s) embedded.")


if __name__ == "__main__":
    main()
