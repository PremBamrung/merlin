"""app_state (migration 013) + the YouTube subtitle cooldown persisted in it.

Runs against the temp DB built by the real Alembic migrations.
"""

import time

from sqlalchemy import inspect

from merlin.core.rate_limit import MinIntervalRateLimiter
from merlin.db.engine import engine, get_db
from merlin.db.repositories.app_state import AppStateRepository
from merlin.knowledge_sources.plugins.youtube import extractors


def test_migration_creates_app_state():
    cols = {c["name"] for c in inspect(engine).get_columns("app_state")}
    assert cols == {"key", "value", "updated_at"}


def test_repository_round_trips_and_overwrites():
    with get_db() as s:
        assert AppStateRepository.get(s, "k") is None
        AppStateRepository.set(s, "k", {"a": 1})
    with get_db() as s:
        assert AppStateRepository.get(s, "k") == {"a": 1}
        AppStateRepository.set(s, "k", {"a": 2})
    with get_db() as s:
        assert AppStateRepository.get(s, "k") == {"a": 2}


def _youtube_limiter():
    # Same hooks as the module-level limiter, on a fresh instance (a "restart").
    return MinIntervalRateLimiter(
        0,
        cooldown_seconds=1800,
        cooldown_max=7200,
        load_state=extractors._load_cooldown_state,
        save_state=extractors._save_cooldown_state,
    )


def test_subtitle_cooldown_survives_restart():
    before = _youtube_limiter()
    assert not before.in_cooldown()
    before.trip_cooldown()

    with get_db() as s:
        state = AppStateRepository.get(s, extractors._COOLDOWN_STATE_KEY)
    assert state["tripped"] is True
    assert state["until"] > time.time() + 1700

    after = _youtube_limiter()
    assert after.in_cooldown()
    after.clear_cooldown()
    assert not _youtube_limiter().in_cooldown()
