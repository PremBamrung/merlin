import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, type UIMessage } from "ai";
import { useCallback } from "react";

/**
 * Chat filters sent alongside the AI SDK message payload (the backend's request
 * model tolerates this extra `filters` field). `item_id` scopes the chat to a
 * single item (Reader); `source_types`/`tags` come from the FilterBar.
 */
export type ChatFilters = {
  source_types?: string[] | null;
  tags?: string[] | null;
  item_id?: string | null;
};

/** A consolidated citation, emitted by the server as a citation data-part. */
export type Citation = {
  item_id: string;
  title: string;
  source_type: string;
  snippet: string;
  score: number;
};

/**
 * The two citation tiers the server emits at end-of-turn:
 * `data-citations` = items the answer actually used (the primary Sources grid);
 * `data-sources-viewed` = items a tool surfaced but the answer didn't cite
 * (a collapsed "Also searched" disclosure).
 */
export const CITATIONS_PART = "data-citations";
export const SOURCES_VIEWED_PART = "data-sources-viewed";

/**
 * Inline citation markers (`[#<id>]`, or `[<id>]` — the `#` is optional because
 * models often drop it) the model writes after sentences. The backend parses
 * them to split used vs viewed sources; on the client we strip them from the
 * rendered/copied answer. Mirrors the server's `_MARKER_RE` (8+ hex/dash chars
 * so prose brackets like `[1]` are never matched).
 */
const MARKER_RE = /\[#?[0-9a-fA-F-]{8,}\]/g;
// Markers the model wrapped in its own parentheses, e.g. "DamsShiro ([id])" or
// "nerfés ([id] [id2])" — strip the whole group so no empty "()" is left behind.
// (Plain "(text)" is untouched: only parens containing *only* markers match.)
const WRAPPED_MARKER_RE = /\(\s*(?:\[#?[0-9a-fA-F-]{8,}\]\s*)+\)/g;
// A marker still mid-stream (closing `]` not yet arrived) at the very end of the
// text — strip it too so a half-typed `[0dd1864…` never flashes during streaming.
const PARTIAL_MARKER_RE = /\[#?[0-9a-fA-F-]*$/;

/** Remove `[#id]` markers from answer text, tidying leftover whitespace. Used
 * for the copy action (clean plain text, no markers). */
export function stripCitationMarkers(text: string): string {
  return text
    .replace(WRAPPED_MARKER_RE, "") // marker-only parens, before bare markers
    .replace(MARKER_RE, "")
    .replace(PARTIAL_MARKER_RE, "")
    .replace(/ +([.,;:!?])/g, "$1") // drop space stranded before punctuation
    .replace(/[ \t]{2,}/g, " "); // collapse double spaces left behind
}

// Same shape as MARKER_RE but capturing the id, for linkifying.
const MARKER_CAPTURE_RE = /\[#?([0-9a-fA-F-]{8,})\]/g;

/** Resolve a marker id (often a UUID prefix) to its index in `citations`. */
function citationIndex(markerId: string, citations: Citation[]): number {
  const id = markerId.toLowerCase();
  let idx = citations.findIndex((c) => c.item_id.toLowerCase() === id);
  if (idx < 0) idx = citations.findIndex((c) => c.item_id.toLowerCase().startsWith(id));
  return idx;
}

/**
 * Rewrite `[#id]`/`[id]` markers into markdown superscript links
 * (`[n](#cite-<item_id>)`) numbered to match the Sources list, so each claim
 * carries a clickable citation. Markers that don't resolve to a known citation
 * — e.g. while the citations list is still streaming in, or a hallucinated id —
 * are dropped. The `#cite-` href is rendered as a chip by `Markdown`.
 */
export function linkifyCitationMarkers(text: string, citations: Citation[]): string {
  if (!citations.length) return stripCitationMarkers(text);
  return text
    .replace(MARKER_CAPTURE_RE, (_full, id: string) => {
      const idx = citationIndex(id, citations);
      return idx >= 0 ? `[${idx + 1}](#cite-${citations[idx].item_id})` : "";
    })
    .replace(PARTIAL_MARKER_RE, "")
    .replace(/ +([.,;:!?])/g, "$1")
    .replace(/[ \t]{2,}/g, " ");
}

// The endpoint is fixed; filters are attached per-send via the request body, so
// one stateless transport instance is shared across every chat surface.
const transport = new DefaultChatTransport({ api: "/api/chat" });

export type UseAgentChatOptions = {
  /** Stable chat/thread id (continuable threads persist under this id). */
  id?: string;
  /** Messages to seed the conversation with when reopening a saved thread. */
  initialMessages?: UIMessage[];
  /**
   * Called when an assistant turn finishes streaming, with the full message
   * list — used to persist the thread. Not fired on abort/disconnect/error so a
   * half-finished turn isn't saved.
   */
  onFinish?: (messages: UIMessage[]) => void;
};

/**
 * Thin wrapper over the Vercel AI SDK `useChat`. The SDK owns the streaming
 * message-parts protocol (text / tool calls / reasoning / data parts), framing,
 * abort, and incremental rendering; we add filter injection, optional
 * persistence seeding/callbacks, and a few ergonomic helpers.
 *
 * For continuable threads the caller passes a stable `id` + `initialMessages`
 * and remounts (via React `key`) on thread switch, so each thread gets a clean
 * `useChat` seeded from its stored history. Omit the options for the ephemeral
 * Reader per-item chat.
 */
export function useAgentChat(opts?: UseAgentChatOptions) {
  const { onFinish } = opts ?? {};
  const chat = useChat({
    transport,
    id: opts?.id,
    messages: opts?.initialMessages,
    onFinish: onFinish
      ? ({ messages, isAbort, isDisconnect, isError }) => {
          if (isAbort || isDisconnect || isError) return;
          onFinish(messages);
        }
      : undefined,
  });
  const { messages, sendMessage, regenerate, status, setMessages } = chat;

  const isStreaming = status === "submitted" || status === "streaming";

  const send = useCallback(
    (text: string, filters?: ChatFilters) => {
      const q = text.trim();
      if (!q || isStreaming) return;
      void sendMessage({ text: q }, { body: { filters: filters ?? null } });
    },
    [sendMessage, isStreaming],
  );

  const regenerateWith = useCallback(
    (filters?: ChatFilters) => {
      if (isStreaming) return;
      void regenerate({ body: { filters: filters ?? null } });
    },
    [regenerate, isStreaming],
  );

  const reset = useCallback(() => {
    chat.stop();
    setMessages([]);
  }, [chat, setMessages]);

  return {
    messages,
    status,
    isStreaming,
    error: chat.error,
    send,
    regenerate: regenerateWith,
    stop: chat.stop,
    reset,
  };
}

export type AgentChat = ReturnType<typeof useAgentChat>;
