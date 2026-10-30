"""Fold a Vercel AI SDK UI-message chunk stream into the assistant `UIMessage`.

A Python port of the AI SDK's `processUIMessageStream`
(`web/node_modules/ai/dist/index.mjs`, `ai@6`), limited to the chunk types our
chat server emits. The server saves the turn it streamed, so it needs the exact
message the browser builds from the same chunks: one assistant message per turn,
`step-start` parts between model requests, tool parts keyed by `toolCallId` with
their state transitions, reasoning, and our `data-*` parts in arrival order.
(`VercelAIAdapter.dump_messages` emits one message per model response instead,
so a saved thread would render differently from the live one.)

Fidelity is pinned by golden tests: real adapter chunk logs, reduced once by the
SDK's own `readUIMessageStream`, in `tests/backend/fixtures/chat_streams/`.

JS `undefined` (a key the SDK leaves unset, dropped when the message is
serialised) is modelled by leaving the key out. Two deliberate gaps, neither of
which our server produces: `dynamic` tools, and the SDK's partial-JSON repair of
half-streamed tool arguments (a delta that doesn't parse yet keeps the last
parsed input).
"""

from __future__ import annotations

import copy
import json
from typing import Any

__all__ = ["ChunkReducer"]

# Stands in for JS `undefined` — "leave this key out".
_UNSET: Any = object()

_RESULT_STATES = ("output-available", "output-error")


def _put(target: dict, key: str, value: Any) -> None:
    """Assign like JS does: an `undefined` value removes the key."""
    if value is _UNSET:
        target.pop(key, None)
    else:
        target[key] = value


def _get(chunk: dict, key: str) -> Any:
    return chunk.get(key, _UNSET)


def _or(value: Any, fallback: Any) -> Any:
    """JS `value ?? fallback`."""
    return fallback if value is _UNSET or value is None else value


def _merge(base: Any, update: Any) -> Any:
    """The SDK's `mergeObjects`: a recursive merge of plain objects; anything
    else is replaced."""
    if not isinstance(base, dict) or not isinstance(update, dict):
        return update
    out = dict(base)
    for key, value in update.items():
        out[key] = _merge(out[key], value) if key in out else value
    return out


def _is_tool_part(part: dict) -> bool:
    return (
        part.get("type", "").startswith("tool-") or part.get("type") == "dynamic-tool"
    )


class ChunkReducer:
    """Feed chunks (decoded JSON dicts, in stream order) with `add`; read the
    assistant message with `message`."""

    def __init__(self, message_id: str = "") -> None:
        self._message: dict[str, Any] = {
            "id": message_id,
            "role": "assistant",
            "parts": [],
        }
        self._active_text: dict[str, dict] = {}
        self._active_reasoning: dict[str, dict] = {}
        self._partial_tools: dict[str, dict] = {}
        self.finish_reason: str | None = None
        self.error_text: str | None = None

    # ------------------------------------------------------------------ #

    @property
    def message(self) -> dict[str, Any]:
        """A deep copy of the message so far."""
        return copy.deepcopy(self._message)

    @property
    def parts(self) -> list[dict]:
        return self._message["parts"]

    def add(self, chunk: dict) -> None:
        kind = chunk.get("type")
        handler = _HANDLERS.get(kind)
        if handler is not None:
            handler(self, chunk)
        elif isinstance(kind, str) and kind.startswith("data-"):
            self._data(chunk)

    def close(self) -> None:
        """Settle a stream that ended early (a Stop or a lost run), so the saved
        message doesn't render as still working: open text/reasoning parts are
        marked done and unfinished tool calls fail as interrupted. Not part of
        the SDK — it would leave them mid-stream."""
        for part in self.parts:
            if (
                part.get("type") in ("text", "reasoning")
                and part.get("state") == "streaming"
            ):
                part["state"] = "done"
            elif _is_tool_part(part) and part.get("state") not in (
                *_RESULT_STATES,
                "output-denied",
            ):
                part["state"] = "output-error"
                part["errorText"] = "Interrupted."
        self._active_text.clear()
        self._active_reasoning.clear()
        self._partial_tools.clear()

    # --- text / reasoning ------------------------------------------------ #

    def _text_start(self, chunk: dict, kind: str, active: dict) -> None:
        part: dict[str, Any] = {"type": kind, "text": ""}
        _put(part, "providerMetadata", _get(chunk, "providerMetadata"))
        part["state"] = "streaming"
        active[chunk["id"]] = part
        self.parts.append(part)

    def _text_delta(self, chunk: dict, active: dict) -> None:
        part = active.get(chunk.get("id"))
        if part is None:
            raise ValueError(f"{chunk['type']} for unknown part {chunk.get('id')!r}")
        part["text"] += chunk.get("delta", "")
        _put(
            part,
            "providerMetadata",
            _or(_get(chunk, "providerMetadata"), part.get("providerMetadata", _UNSET)),
        )

    def _text_end(self, chunk: dict, active: dict) -> None:
        part = active.pop(chunk.get("id"), None)
        if part is None:
            raise ValueError(f"{chunk['type']} for unknown part {chunk.get('id')!r}")
        part["state"] = "done"
        _put(
            part,
            "providerMetadata",
            _or(_get(chunk, "providerMetadata"), part.get("providerMetadata", _UNSET)),
        )

    # --- tools ----------------------------------------------------------- #

    def _find_tool(self, tool_call_id: str) -> dict | None:
        return next(
            (
                p
                for p in self.parts
                if _is_tool_part(p) and p.get("toolCallId") == tool_call_id
            ),
            None,
        )

    def _update_tool(
        self,
        *,
        tool_call_id: str,
        tool_name: str,
        state: str,
        input: Any = _UNSET,
        output: Any = _UNSET,
        raw_input: Any = _UNSET,
        error_text: Any = _UNSET,
        provider_executed: Any = _UNSET,
        preliminary: Any = _UNSET,
        title: Any = _UNSET,
        tool_metadata: Any = _UNSET,
        provider_metadata: Any = _UNSET,
    ) -> None:
        """The SDK's `updateToolPart`: every field is reassigned on update, so
        an omitted one is cleared (except title/toolMetadata/providerExecuted)."""
        is_result = state in _RESULT_STATES
        part = self._find_tool(tool_call_id)
        if part is not None:
            part["state"] = state
            _put(part, "input", input)
            _put(part, "output", output)
            _put(part, "errorText", error_text)
            _put(part, "rawInput", raw_input)
            _put(part, "preliminary", preliminary)
            if title is not _UNSET:
                part["title"] = title
            if tool_metadata is not _UNSET:
                part["toolMetadata"] = tool_metadata
            _put(
                part,
                "providerExecuted",
                _or(provider_executed, part.get("providerExecuted", _UNSET)),
            )
            if provider_metadata is not _UNSET and provider_metadata is not None:
                key = "resultProviderMetadata" if is_result else "callProviderMetadata"
                part[key] = provider_metadata
            return

        part = {"type": f"tool-{tool_name}", "toolCallId": tool_call_id, "state": state}
        _put(part, "title", title)
        _put(part, "toolMetadata", tool_metadata)
        _put(part, "input", input)
        _put(part, "output", output)
        _put(part, "rawInput", raw_input)
        _put(part, "errorText", error_text)
        _put(part, "providerExecuted", provider_executed)
        _put(part, "preliminary", preliminary)
        if provider_metadata is not _UNSET and provider_metadata is not None:
            key = "resultProviderMetadata" if is_result else "callProviderMetadata"
            part[key] = provider_metadata
        self.parts.append(part)

    def _tool_input_start(self, chunk: dict) -> None:
        self._partial_tools[chunk["toolCallId"]] = {
            "text": "",
            "toolName": chunk["toolName"],
            "title": _get(chunk, "title"),
            "toolMetadata": _get(chunk, "toolMetadata"),
        }
        self._update_tool(
            tool_call_id=chunk["toolCallId"],
            tool_name=chunk["toolName"],
            state="input-streaming",
            provider_executed=_get(chunk, "providerExecuted"),
            title=_get(chunk, "title"),
            tool_metadata=_get(chunk, "toolMetadata"),
            provider_metadata=_get(chunk, "providerMetadata"),
        )

    def _tool_input_delta(self, chunk: dict) -> None:
        partial = self._partial_tools.get(chunk.get("toolCallId"))
        if partial is None:
            raise ValueError(
                f"tool-input-delta for unknown call {chunk.get('toolCallId')!r}"
            )
        partial["text"] += chunk.get("inputTextDelta", "")
        try:
            args = json.loads(partial["text"])
        except ValueError:
            existing = self._find_tool(chunk["toolCallId"]) or {}
            args = existing.get("input", _UNSET)
        self._update_tool(
            tool_call_id=chunk["toolCallId"],
            tool_name=partial["toolName"],
            state="input-streaming",
            input=args,
            title=partial["title"],
            tool_metadata=partial["toolMetadata"],
        )

    def _tool_input_available(self, chunk: dict) -> None:
        self._update_tool(
            tool_call_id=chunk["toolCallId"],
            tool_name=chunk["toolName"],
            state="input-available",
            input=_get(chunk, "input"),
            provider_executed=_get(chunk, "providerExecuted"),
            provider_metadata=_get(chunk, "providerMetadata"),
            title=_get(chunk, "title"),
            tool_metadata=_get(chunk, "toolMetadata"),
        )

    def _tool_input_error(self, chunk: dict) -> None:
        self._update_tool(
            tool_call_id=chunk["toolCallId"],
            tool_name=chunk["toolName"],
            state="output-error",
            raw_input=_get(chunk, "input"),
            error_text=_get(chunk, "errorText"),
            provider_executed=_get(chunk, "providerExecuted"),
            provider_metadata=_get(chunk, "providerMetadata"),
            tool_metadata=_get(chunk, "toolMetadata"),
        )

    def _tool_result(self, chunk: dict, state: str) -> None:
        part = self._find_tool(chunk.get("toolCallId"))
        if part is None:
            raise ValueError(
                f"{chunk['type']} for unknown call {chunk.get('toolCallId')!r}"
            )
        self._update_tool(
            tool_call_id=chunk["toolCallId"],
            tool_name=part["type"].removeprefix("tool-"),
            state=state,
            input=part.get("input", _UNSET),
            output=_get(chunk, "output") if state == "output-available" else _UNSET,
            raw_input=part.get("rawInput", _UNSET)
            if state == "output-error"
            else _UNSET,
            error_text=_get(chunk, "errorText") if state == "output-error" else _UNSET,
            provider_executed=_get(chunk, "providerExecuted"),
            preliminary=_get(chunk, "preliminary")
            if state == "output-available"
            else _UNSET,
            provider_metadata=_get(chunk, "providerMetadata"),
            title=part.get("title", _UNSET),
            tool_metadata=part.get("toolMetadata", _UNSET),
        )

    def _tool_set_state(self, chunk: dict, state: str) -> None:
        part = self._find_tool(chunk.get("toolCallId"))
        if part is None:
            raise ValueError(
                f"{chunk['type']} for unknown call {chunk.get('toolCallId')!r}"
            )
        part["state"] = state
        if state == "approval-requested":
            approval = {"id": chunk.get("approvalId")}
            if chunk.get("signature") is not None:
                approval["signature"] = chunk["signature"]
            part["approval"] = approval

    # --- message-level --------------------------------------------------- #

    def _metadata(self, metadata: Any) -> None:
        if metadata is _UNSET or metadata is None:
            return
        current = self._message.get("metadata")
        self._message["metadata"] = (
            _merge(current, metadata) if current is not None else metadata
        )

    def _start(self, chunk: dict) -> None:
        if chunk.get("messageId") is not None:
            self._message["id"] = chunk["messageId"]
        self._metadata(_get(chunk, "messageMetadata"))

    def _finish_step(self, _chunk: dict) -> None:
        self._active_text = {}
        self._active_reasoning = {}

    def _finish(self, chunk: dict) -> None:
        if chunk.get("finishReason") is not None:
            self.finish_reason = chunk["finishReason"]
        self._metadata(_get(chunk, "messageMetadata"))

    def _error(self, chunk: dict) -> None:
        self.error_text = chunk.get("errorText") or ""

    def _data(self, chunk: dict) -> None:
        if chunk.get("transient"):
            return
        if chunk.get("id") is not None:
            existing = next(
                (
                    p
                    for p in self.parts
                    if p.get("type") == chunk["type"] and p.get("id") == chunk["id"]
                ),
                None,
            )
            if existing is not None:
                existing["data"] = chunk.get("data")
                return
        self.parts.append(copy.deepcopy(chunk))

    def _passthrough(self, chunk: dict, keys: tuple[str, ...]) -> None:
        part = {"type": chunk["type"]}
        for key in keys:
            _put(part, key, _get(chunk, key))
        self.parts.append(part)


_HANDLERS = {
    "text-start": lambda r, c: r._text_start(c, "text", r._active_text),
    "text-delta": lambda r, c: r._text_delta(c, r._active_text),
    "text-end": lambda r, c: r._text_end(c, r._active_text),
    "reasoning-start": lambda r, c: r._text_start(c, "reasoning", r._active_reasoning),
    "reasoning-delta": lambda r, c: r._text_delta(c, r._active_reasoning),
    "reasoning-end": lambda r, c: r._text_end(c, r._active_reasoning),
    "file": lambda r, c: r._passthrough(c, ("mediaType", "url", "providerMetadata")),
    "source-url": lambda r, c: r._passthrough(
        c, ("sourceId", "url", "title", "providerMetadata")
    ),
    "source-document": lambda r, c: r._passthrough(
        c, ("sourceId", "mediaType", "title", "filename", "providerMetadata")
    ),
    "tool-input-start": ChunkReducer._tool_input_start,
    "tool-input-delta": ChunkReducer._tool_input_delta,
    "tool-input-available": ChunkReducer._tool_input_available,
    "tool-input-error": ChunkReducer._tool_input_error,
    "tool-approval-request": lambda r, c: r._tool_set_state(c, "approval-requested"),
    "tool-output-denied": lambda r, c: r._tool_set_state(c, "output-denied"),
    "tool-output-available": lambda r, c: r._tool_result(c, "output-available"),
    "tool-output-error": lambda r, c: r._tool_result(c, "output-error"),
    "start-step": lambda r, c: r.parts.append({"type": "step-start"}),
    "finish-step": ChunkReducer._finish_step,
    "start": ChunkReducer._start,
    "finish": ChunkReducer._finish,
    "message-metadata": lambda r, c: r._metadata(_get(c, "messageMetadata")),
    "error": ChunkReducer._error,
}
