"""Backfill semantic-search vectors for already-ingested library items.

Thin CLI wrapper over `merlin.services.embeddings.heal_missing_embeddings` (the
same self-heal that runs automatically on app startup). Use it when you want to
fill the backlog on demand from a shell rather than waiting for the startup pass.

Embeds every completed item that has no stored vector yet (one vector per item,
built from title + tags + summary). Requires a configured embedding provider;
with `EMBEDDING_PROVIDER=none` it does nothing. The engine binds to
`settings.database_url` at import, so point it at the real DB with the env var
(matching the rest of the project) rather than a flag:

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
from pathlib import Path
import sys

# Running a script puts scripts/ (not the repo root) on sys.path; add the root
# so `import merlin` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from merlin.rag.embeddings import get_embedder  # noqa: E402
from merlin.services.embeddings import (  # noqa: E402
    heal_missing_embeddings,
    pending_items,
)


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

    if args.dry_run:
        pending = pending_items(args.limit)
        if not pending:
            print("Nothing to backfill — all completed items already have vectors.")
            return
        print(f"{len(pending)} item(s) to embed with {embedder.model}:")
        for it in pending[:10]:
            print(f"  - {it['id']}  {it['title'][:70]!r}")
        if len(pending) > 10:
            print(f"  … and {len(pending) - 10} more")
        print("Dry run — no API calls made, nothing written.")
        return

    result = heal_missing_embeddings(
        batch=args.batch,
        limit=args.limit,
        max_retries=args.max_retries,
        sleep=args.sleep,
        on_progress=lambda done, total: print(f"  embedded {done}/{total}"),
    )
    if result["pending"] == 0:
        print("Nothing to backfill — all completed items already have vectors.")
    else:
        print(f"Done — {result['embedded']} item(s) embedded.")


if __name__ == "__main__":
    main()
