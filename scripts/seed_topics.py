"""Seed a starter topic taxonomy so the Feed filter is useful from day one.

On a cold start the topic list is empty, so a classify/backfill run would leave
almost everything uncategorised. Seeding 6–8 obvious buckets first means most
items snap to a seed at classify time; the rest stay uncategorised for the batch
proposal pipeline to name (docs/TOPICS_AND_TAGS_PLAN.md §8).

Idempotent — skips a topic whose slug already exists, so it is safe to re-run
(and to extend the SEED list later). The engine binds to `settings.database_url`
at import, so point it at the real DB with the env var:

    DATABASE_URL="sqlite:///$(pwd)/data/merlin.db" \\
        uv run python scripts/seed_topics.py

Edit SEED to match your own interests before the first run.
"""

from __future__ import annotations

from pathlib import Path
import sys

# Running a script puts scripts/ (not the repo root) on sys.path; add the root
# so `import merlin` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from merlin.db.engine import SessionFactory  # noqa: E402
from merlin.db.repositories.topics import TopicRepository  # noqa: E402
from merlin.services.topics import slugify  # noqa: E402

# (label, description) — the description is an optional disambiguator that is
# also fed to the classifier prompt, so keep it short and concrete.
SEED: list[tuple[str, str]] = [
    ("Coding", "software, programming, dev tools, frameworks"),
    ("Gaming", "video games generally"),
    ("Dofus", "the game Dofus specifically"),
    ("Healthcare", "health, medicine, fitness, nutrition"),
    ("Sport", "sports and athletics"),
    ("AI & ML", "artificial intelligence, machine learning, LLMs"),
    ("Finance", "money, investing, markets, personal finance"),
    ("Science", "physics, biology, space, research"),
]


def main() -> None:
    created, skipped = 0, 0
    with SessionFactory() as session:
        for label, description in SEED:
            slug = slugify(label)
            if TopicRepository.get_by_slug(session, slug) is not None:
                skipped += 1
                continue
            TopicRepository.create(
                session,
                label=label,
                slug=slug,
                origin="seed",
                description=description,
            )
            created += 1
        session.commit()
    print(f"Seeded {created} topic(s), skipped {skipped} existing.")


if __name__ == "__main__":
    main()
