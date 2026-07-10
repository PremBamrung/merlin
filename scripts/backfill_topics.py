"""Backfill topic + tag classification for already-ingested library items.

Mirrors scripts/backfill_embeddings.py. Iterates completed items that have no
topic assignment yet and runs `merlin.services.classify.classify_and_persist`
from each item's STORED summary — no re-transcription, one cheap LLM call each.

Idempotent: an item that gets classified gains an item_topics row and won't be
picked up again. An item that genuinely fits no active topic stays uncategorised
(and would be retried on a later run) — seed a starter taxonomy first
(scripts/seed_topics.py) so most items snap to a topic, and use the batch
proposal pipeline for the rest (docs/TOPICS_AND_TAGS_PLAN.md §8).

The engine binds to `settings.database_url` at import, so point it at the real
DB with the env var (matching the rest of the project):

    DATABASE_URL="sqlite:///$(pwd)/data/merlin.db" \\
        uv run python scripts/backfill_topics.py

    # preview the work, no LLM calls, no writes:
    DATABASE_URL="sqlite:///$(pwd)/data/merlin.db" \\
        uv run python scripts/backfill_topics.py --dry-run

Options:
    --limit N    stop after N items (default: all)
    --sleep S    seconds to pause between items (default 0)
    --dry-run    report the work and exit without calling the LLM or writing
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

# Running a script puts scripts/ (not the repo root) on sys.path; add the root
# so `import merlin` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from merlin.db.engine import SessionFactory  # noqa: E402
from merlin.db.repositories.topics import TopicRepository  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None, help="max items to classify")
    ap.add_argument("--sleep", type=float, default=0.0, help="pause between items")
    ap.add_argument("--dry-run", action="store_true", help="report only, no writes")
    args = ap.parse_args()

    with SessionFactory() as session:
        items = TopicRepository.uncategorised_items(session, limit=args.limit)
        ids = [(i.id, i.title) for i in items]
        active = TopicRepository.list_active(session)

    print(f"{len(ids)} uncategorised item(s); {len(active)} active topic(s).")
    if not active:
        print(
            "WARNING: no active topics — every item will stay uncategorised. "
            "Seed some first (scripts/seed_topics.py) or use the proposal pipeline."
        )
    if args.dry_run:
        for item_id, title in ids[:20]:
            print(f"  would classify {item_id}  {title!r}")
        if len(ids) > 20:
            print(f"  … and {len(ids) - 20} more")
        return

    from merlin.services.classify import classify_and_persist

    done = 0
    for item_id, _title in ids:
        classify_and_persist(item_id)
        done += 1
        if done % 25 == 0 or done == len(ids):
            print(f"  classified {done}/{len(ids)}")
        if args.sleep:
            time.sleep(args.sleep)
    print(f"Done. Classified {done} item(s).")


if __name__ == "__main__":
    main()
