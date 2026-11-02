"""Runtime-tunable settings: env defaults, overridable from the Settings page.

A small, fixed set of behaviour knobs (thinking levels, the chat search budget,
model aliases) that are worth changing without a redeploy. Each knob's default
is its env value from `merlin.config.settings`; an override saved from the UI
lives in the `app_state` table under one key and wins until it's reset.

Infrastructure and secrets (API keys, base URLs, the provider) are deliberately
NOT here — they stay env-only.

Reads go to SQLite every time (one primary-key lookup — cheap, and never stale
across workers). If the DB isn't reachable (no migrations yet, a unit test
without a schema), every knob falls back to its env default.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from merlin.config import settings
from merlin.core.logging import logger

THINKING_LEVELS = ("minimal", "low", "medium", "high")

# Library chat's first step of each turn — deciding what to search — runs at no
# more than this level by default; only steps with tool results in hand (judging
# them, writing the answer) use the composer's level. Each Gemini Flash step at
# medium cost ~4s more than at low (measured 2026-11-02 via the proxy: median
# first text 1.6s at low vs 5.7s at medium), paid per step of the tool loop.
DEFAULT_SEARCH_STEP_THINKING = "low"

_STATE_KEY = "settings"


@dataclass(frozen=True)
class Tunable:
    key: str
    kind: str  # "thinking" | "int" | "model"
    default: Callable[[], Any]
    min: int | None = None
    max: int | None = None


TUNABLES: dict[str, Tunable] = {
    t.key: t
    for t in (
        Tunable(
            "summarize_thinking", "thinking", lambda: settings.ingest_thinking_level
        ),
        Tunable(
            "classify_thinking", "thinking", lambda: settings.classify_thinking_level
        ),
        Tunable(
            "discover_thinking", "thinking", lambda: settings.discover_thinking_level
        ),
        Tunable(
            "search_step_thinking", "thinking", lambda: DEFAULT_SEARCH_STEP_THINKING
        ),
        Tunable(
            "chat_max_requests",
            "int",
            lambda: settings.chat_max_requests,
            min=1,
            max=50,
        ),
        Tunable("chat_model", "model", lambda: settings.chat_model_name),
        Tunable("ingest_model", "model", lambda: settings.ingest_model_name),
        # Derived, not shown as a knob: the context window of an overridden chat
        # model (looked up when it's picked), so the context meter stays right.
        Tunable(
            "chat_context_window",
            "int",
            lambda: settings.chat_context_window,
            min=0,
            max=100_000_000,
        ),
    )
}


def overrides() -> dict[str, Any]:
    """The saved overrides (`{}` when none, or when the DB isn't available)."""
    from merlin.db.engine import get_db
    from merlin.db.repositories.app_state import AppStateRepository

    try:
        with get_db() as session:
            raw = AppStateRepository.get(session, _STATE_KEY)
    except Exception as exc:  # no schema yet, DB unreachable — use env defaults
        logger.debug(f"tunables: overrides unavailable ({exc}); using env defaults")
        return {}
    return {k: v for k, v in (raw or {}).items() if k in TUNABLES}


def default(key: str) -> Any:
    return TUNABLES[key].default()


def get(key: str) -> Any:
    """The effective value of `key`: its override if saved, else the env default."""
    saved = overrides()
    return saved[key] if key in saved else default(key)


def validate(key: str, value: Any) -> Any:
    """`value` normalised for `key`; raises ValueError if it isn't valid."""
    t = TUNABLES.get(key)
    if t is None:
        raise ValueError(f"Unknown setting: {key}")
    if t.kind == "thinking":
        level = str(value).strip().lower() if isinstance(value, str) else None
        if level not in THINKING_LEVELS:
            raise ValueError(f"{key} must be one of {', '.join(THINKING_LEVELS)}.")
        return level
    if t.kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{key} must be a whole number.")
        if (t.min is not None and value < t.min) or (
            t.max is not None and value > t.max
        ):
            raise ValueError(f"{key} must be between {t.min} and {t.max}.")
        return value
    # model
    name = value.strip() if isinstance(value, str) else ""
    if not name or len(name) > 200:
        raise ValueError(f"{key} must be a model name.")
    return name


def update(patch: dict[str, Any]) -> dict[str, Any]:
    """Apply `patch` (key → value, or None to reset to default) atomically.

    Every value is validated before anything is written; returns the new
    overrides.
    """
    from merlin.db.engine import get_db
    from merlin.db.repositories.app_state import AppStateRepository

    cleaned = {
        k: (None if v is None else validate(k, v)) for k, v in (patch or {}).items()
    }
    with get_db() as session:
        current = {
            k: v
            for k, v in (AppStateRepository.get(session, _STATE_KEY) or {}).items()
            if k in TUNABLES
        }
        for k, v in cleaned.items():
            if v is None:
                current.pop(k, None)
            else:
                current[k] = v
        AppStateRepository.set(session, _STATE_KEY, current)
    return current


def reset_all() -> None:
    """Drop every override (tests; a "reset everything" action)."""
    from merlin.db.engine import get_db
    from merlin.db.repositories.app_state import AppStateRepository

    with get_db() as session:
        AppStateRepository.set(session, _STATE_KEY, {})
