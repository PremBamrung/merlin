"""App settings — the Settings page's view of the runtime-tunable knobs.

Wraps `merlin.core.tunables` (env defaults + saved overrides) with what the UI
needs: each knob's effective value, default and options, plus the model aliases
the LiteLLM proxy serves. Returns plain dicts.
"""

from __future__ import annotations

from typing import Any

import httpx

from merlin.config import settings
from merlin.core import tunables
from merlin.core.logging import logger

# The knobs the page shows, in order. `chat_context_window` is derived (set when
# the chat model is picked), so it's not listed.
_SECTIONS: list[tuple[str, list[str]]] = [
    (
        "thinking",
        [
            "summarize_thinking",
            "classify_thinking",
            "discover_thinking",
            "search_step_thinking",
        ],
    ),
    ("chat", ["chat_max_requests"]),
    ("models", ["chat_model", "ingest_model"]),
]

_MODELS_TIMEOUT = 5.0


def effective(key: str) -> Any:
    """The effective value of one knob (override, else env default)."""
    return tunables.get(key)


def list_models() -> dict:
    """Chat-capable model aliases the LiteLLM proxy serves (not the web-search
    alias), each with its context window. `available` is False when the
    provider isn't LiteLLM or the proxy can't be reached."""
    if not settings.is_litellm or not settings.litellm_base_url:
        return {"available": False, "models": []}
    url = settings.litellm_base_url.rstrip("/") + "/models"
    headers = (
        {"Authorization": f"Bearer {settings.litellm_api_key}"}
        if settings.litellm_api_key
        else {}
    )
    try:
        resp = httpx.get(url, headers=headers, timeout=_MODELS_TIMEOUT)
        resp.raise_for_status()
        data = resp.json().get("data") or []
    except Exception as exc:
        logger.warning(f"app_settings: model list unavailable ({exc})")
        return {"available": False, "models": []}
    models = [
        {
            "id": m["id"],
            "context_window": m.get("max_input_tokens"),
        }
        for m in data
        if m.get("id")
        and m["id"] != settings.litellm_web_search_model
        and m.get("mode", "chat") == "chat"
    ]
    return {"available": True, "models": models}


def get_settings() -> dict:
    """Every visible knob: value, env default, whether it's overridden, and its
    options — grouped by section — plus whether thinking control applies."""
    saved = tunables.overrides()
    sections = []
    for section, keys in _SECTIONS:
        items = []
        for key in keys:
            t = tunables.TUNABLES[key]
            item = {
                "key": key,
                "kind": t.kind,
                "value": saved.get(key, tunables.default(key)),
                "default": tunables.default(key),
                "overridden": key in saved,
                "min": t.min,
                "max": t.max,
                "options": list(tunables.THINKING_LEVELS)
                if t.kind == "thinking"
                else None,
            }
            items.append(item)
        sections.append({"id": section, "settings": items})
    return {
        "provider": settings.llm_provider_name,
        "thinking_supported": settings.is_litellm,
        "sections": sections,
    }


def update_settings(patch: dict[str, Any]) -> dict:
    """Apply a partial update (value, or None to reset) and return the page.

    Picking a chat model also records its context window (from the proxy's
    model list) so the context meter stays right; resetting it drops that.
    Raises ValueError for an unknown key or an invalid value.
    """
    patch = dict(patch or {})
    if "chat_context_window" in patch:
        raise ValueError("Unknown setting: chat_context_window")
    for key in patch:
        if key not in tunables.TUNABLES:
            raise ValueError(f"Unknown setting: {key}")
    if "chat_model" in patch:
        patch["chat_context_window"] = _context_window_for(patch["chat_model"])
    tunables.update(patch)
    return get_settings()


def _context_window_for(model: str | None) -> int | None:
    """The proxy-reported context window of `model`, or None (→ env default)."""
    if model is None:
        return None
    for m in list_models()["models"]:
        if m["id"] == str(model).strip():
            window = m.get("context_window")
            return window if isinstance(window, int) and window > 0 else None
    return None
