"""Static pricing map → USD cost for a usage record (FALLBACK ONLY).

The **primary** cost source is the provider's own reported spend: OpenRouter
bills usage on the response (token LLMs return it inline in LangChain's
`response_metadata`, and the chat path reads it back from the /generation
endpoint). Use this map only when the provider doesn't report a cost — Azure
token calls, and Groq audio transcription (which has no cost passthrough, so its
cost is *always* computed here from audio duration).

The numbers are **estimates stamped with an as-of date** — they WILL go stale as
providers change pricing. `cost()` returns ``None`` for any token model not in
the map so the caller stores NULL and Insights shows "unknown" rather than a
wrong $0 (audio always prices via the per-hour rate).

Token prices are USD per 1M tokens. Audio is USD per hour of input audio.
"""

from __future__ import annotations

# As-of date for the figures below. Bump this whenever you revise a price.
PRICING_AS_OF = "2026-06"

# USD per 1,000,000 tokens. {"in": input price, "out": output price}.
# NOTE: estimates — verify against the provider's current pricing page.
TOKEN_PRICING: dict[str, dict[str, float]] = {
    # OpenRouter (model ids as passed to OpenRouter).
    "deepseek/deepseek-v4-flash": {"in": 0.10, "out": 0.30},
    "deepseek/deepseek-chat": {"in": 0.14, "out": 0.28},
    "anthropic/claude-3.5-sonnet": {"in": 3.00, "out": 15.00},
    "openai/gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "openai/gpt-4o": {"in": 2.50, "out": 10.00},
}

# USD per hour of audio (Groq Whisper transcription).
AUDIO_PRICING_PER_HOUR: dict[str, float] = {
    # Groq whisper-large-v3 / turbo — estimate.
    "whisper-large-v3": 0.111,
    "whisper-large-v3-turbo": 0.04,
}

# Used when a transcribe row has no explicit model (older / generic Groq calls).
_DEFAULT_AUDIO_PER_HOUR = 0.04


def token_cost(
    model: str | None, input_tokens: int, output_tokens: int
) -> float | None:
    """USD for a token-billed call, or None if the model isn't priced."""
    if not model:
        return None
    rates = TOKEN_PRICING.get(model)
    if rates is None:
        return None
    return (input_tokens / 1_000_000) * rates["in"] + (
        output_tokens / 1_000_000
    ) * rates["out"]


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
        return token_cost(model, input_tokens, output_tokens)
    return None
