"""Static pricing map → USD cost for a usage record.

Who uses it:
- **summarise + classify** — Pydantic AI doesn't surface OpenRouter's per-call
  cost, so these price off this map using the *resolved* model the response
  reports (e.g. `deepseek/deepseek-v4-flash`, not our `@preset/…` id).
- **chat** — reads authoritative spend back from OpenRouter's /generation
  endpoint, falling back to this map when the lookup lags/fails.
- **Groq audio transcription** — no cost passthrough, so it is *always* computed
  here from audio duration.

The numbers are **estimates stamped with an as-of date** — they WILL go stale as
providers change pricing. `cost()` returns ``None`` for any token model not in
the map so the caller stores NULL and Insights shows "unknown" rather than a
wrong $0 (audio always prices via the per-hour rate).

Token prices are USD per 1M tokens. Audio is USD per hour of input audio.
"""

from __future__ import annotations

# As-of date for the figures below. Bump this whenever you revise a price.
PRICING_AS_OF = "2026-06"

# USD per 1,000,000 tokens. {"in": input, "out": output, "cache_read": optional
# discounted rate for prompt-cache hits}. NOTE: estimates — verify against the
# provider's current pricing page.
# `cache_read` matters a lot for multi-turn chat: each turn re-sends the whole
# conversation, almost all of which is a cache hit on turn 2+. Pricing those
# tokens at the full `in` rate overstates cost several-fold, so when the model
# reports cached tokens we bill them at `cache_read` instead (see `token_cost`).
TOKEN_PRICING: dict[str, dict[str, float]] = {
    # OpenRouter (model ids as passed to OpenRouter). deepseek-v4-flash figures
    # are for the pinned DeepSeek provider (our preset routes only to it).
    "deepseek/deepseek-v4-flash": {"in": 0.14, "out": 0.28, "cache_read": 0.0028},
    "deepseek/deepseek-chat": {"in": 0.14, "out": 0.28},
    "anthropic/claude-3.5-sonnet": {"in": 3.00, "out": 15.00},
    "openai/gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "openai/gpt-4o": {"in": 2.50, "out": 10.00},
}


def _resolve_rates(model: str | None) -> dict[str, float] | None:
    """Rates for a model id, tolerating version suffixes / resolved names.

    The chat agent's configured id is an OpenRouter preset (`@preset/…`), which
    never matches a map key — but the *response* reports the resolved underlying
    model (e.g. `deepseek/deepseek-v4-flash-20260423`). We price off that, so an
    exact miss falls back to the longest map key that the id starts with. The
    preset id itself still resolves to None (correctly unpriced)."""
    if not model:
        return None
    if model in TOKEN_PRICING:
        return TOKEN_PRICING[model]
    matches = [key for key in TOKEN_PRICING if model.startswith(key)]
    if not matches:
        return None
    return TOKEN_PRICING[max(matches, key=len)]


# USD per hour of audio (Groq Whisper transcription).
AUDIO_PRICING_PER_HOUR: dict[str, float] = {
    # Groq whisper-large-v3 / turbo — estimate.
    "whisper-large-v3": 0.111,
    "whisper-large-v3-turbo": 0.04,
}

# Used when a transcribe row has no explicit model (older / generic Groq calls).
_DEFAULT_AUDIO_PER_HOUR = 0.04


def token_cost(
    model: str | None,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
) -> float | None:
    """USD for a token-billed call, or None if the model isn't priced.

    `input_tokens` is the *full* prompt count (the provider's `prompt_tokens`
    already includes cache hits), and `cache_read_tokens` is the cached subset.
    When the model has a `cache_read` rate we bill the cached tokens at it and
    only the uncached remainder at the full `in` rate; otherwise everything is
    billed at `in` (the historical behaviour, unchanged for un-cached calls)."""
    rates = _resolve_rates(model)
    if rates is None:
        return None
    cached = min(max(cache_read_tokens, 0), input_tokens)
    uncached = input_tokens - cached
    cache_rate = rates.get("cache_read", rates["in"])
    return (
        uncached * rates["in"] + cached * cache_rate + output_tokens * rates["out"]
    ) / 1_000_000


def audio_cost(model: str | None, audio_seconds: float) -> float | None:
    """USD for an audio-billed (transcription) call, or None if unpriced."""
    if not audio_seconds:
        return None
    per_hour = AUDIO_PRICING_PER_HOUR.get(model or "", _DEFAULT_AUDIO_PER_HOUR)
    return (audio_seconds / 3600.0) * per_hour


def cost(
    provider: str | None,
    model: str | None,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    audio_seconds: float = 0.0,
) -> float | None:
    """Best-effort USD cost from the pricing map.

    Returns None when nothing can be priced (unknown token model and no audio),
    so the caller persists NULL. `provider` is accepted for symmetry / future
    per-provider rates; pricing is keyed on `model` today.
    """
    if audio_seconds:
        return audio_cost(model, audio_seconds)
    if input_tokens or output_tokens:
        return token_cost(model, input_tokens, output_tokens, cache_read_tokens)
    return None
