import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, type UIMessage } from "ai";
import { useCallback, useEffect, useRef } from "react";
import { useUi, type ThinkingLevel } from "@/store/ui";

/**
 * Chat filters sent alongside the AI SDK message payload (the backend's request
 * model tolerates this extra `filters` field). `item_id` scopes the chat to a
 * single item (Reader); `source_types`/`tags` come from the FilterBar.
 */
export type ChatFilters = {
  source_types?: string[] | null;
  tags?: string[] | null;
  item_id?: string | null;
  /** Thinking level for this message — attached by `useAgentChat` from the
   * stored preference; the backend ignores it when unsupported. */
  thinking?: ThinkingLevel | null;
};

/** The request body for a send: the caller's filters plus the stored thinking
 * level for its surface (the Reader's when `item_id` scopes it to one item, the
 * library chat's otherwise), read at send time so a picker change applies to
 * the next message.
 * `tz` and `sent_at` let the agent see when each message was written: `sent_at`
 * is the same epoch ms the user message is stamped with at end-of-turn, so the
 * model sees an identical stamp on later turns (prompt-cache stable). */
function thinkingFor(filters: ChatFilters | undefined): ThinkingLevel {
  const s = useUi.getState();
  return filters?.item_id ? s.readerThinking : s.chatThinking;
}

function requestBody(filters: ChatFilters | undefined, sentAt: number) {
  return {
    filters: { ...filters, thinking: thinkingFor(filters) },
    tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
    sent_at: sentAt,
  };
}

/** A consolidated citation, emitted by the server as a citation data-part.
 * The card fields (thumbnail…source_id) are added by the chat router for the
 * source cards; threads saved before that carry only the first five. */
export type Citation = {
  item_id: string;
  title: string;
  source_type: string;
  snippet: string;
  score: number;
  thumbnail_url?: string | null;
  channel?: string | null;
  published_at?: string | null;
  duration?: number | string | null;
  source_id?: string | null;
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
 * Per-turn usage emitted by the server at end-of-turn: token counts, an
 * estimated cost, and context-window occupancy. `context_used` is the *last*
 * request's prompt + answer (how full the window has grown — not the tool
 * loop's summed tokens); `context_limit` is the model's window (null ⇒ unknown,
 * hide the %). Rides in the assistant message parts so it persists with the
 * thread, exactly like the citation parts.
 */
export const USAGE_PART = "data-usage";
export type TurnUsage = {
  input_tokens: number | null;
  output_tokens: number | null;
  cache_read_tokens: number | null;
  requests: number | null;
  cost_usd: number | null;
  cost_estimated: boolean;
  context_used: number | null;
  context_limit: number | null;
};

/** A message's persisted turn-usage data-part, if it carries one. */
export function messageUsage(message: UIMessage): TurnUsage | null {
  const parts = (message.parts ?? []) as { type: string; data?: TurnUsage }[];
  return parts.find((p) => p.type === USAGE_PART)?.data ?? null;
}

/** The most recent turn's usage in a message list — drives the composer meter.
 * Walks from the end; null until the first turn finishes (data-usage lands at
 * end-of-turn, so the meter simply doesn't show before then). */
export function latestUsage(messages: UIMessage[]): TurnUsage | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    const u = messageUsage(messages[i]);
    if (u) return u;
  }
  return null;
}
/**
 * The wall-clock duration (whole seconds) of a turn's "work" phase — from send
 * until the assistant's first answer text streams in. The live `WorkTrace`
 * timer is client-only and lost on refresh, so we capture this on finish and
 * persist it as a data-part; on reload the work block reads it back.
 */
export const WORK_TIMING_PART = "data-work-timing";

/**
 * Per-message wall-clock timestamp (epoch ms), stamped at end-of-turn and
 * persisted as a data-part — so a message's time survives reload with no schema
 * change (the DB column can't be used: each save wipes and re-inserts rows). The
 * adapter skips `data-*` parts when replaying history, so this round-trips
 * harmlessly on continuation turns — the chat route reads the user messages'
 * stamps itself and prefixes each prompt with its send time for the agent. The
 * user message is stamped with the turn's send time, the assistant message
 * with the finish time.
 */
export const MESSAGE_TIME_PART = "data-message-time";

/**
 * How a library turn ended early, when it did: the server adds this part to an
 * answer that errored, hit its step limit, or was stopped, so a reopened thread
 * shows why the answer is partial.
 */
export const ERROR_PART = "data-error";
export type TurnError = { reason: "stopped" | "error"; message: string };

/** A message's `data-error` part, if it ended early. */
export function messageError(message: UIMessage): TurnError | null {
  const parts = (message.parts ?? []) as { type: string; data?: TurnError }[];
  return parts.find((p) => p.type === ERROR_PART)?.data ?? null;
}

// Citation-marker helpers live in a dependency-free module (the Home route
// uses them without the AI SDK); re-exported here for the chat components.
export {
  citeAnchorId,
  linkifyCitationMarkers,
  stripCitationMarkers,
} from "@/lib/citationMarkers";

/** True for a reasoning or tool-call part (the parts a `WorkTrace` groups). */
function isWorkPart(p: { type: string }): boolean {
  return p.type === "reasoning" || p.type === "dynamic-tool" || p.type.startsWith("tool-");
}

/**
 * Annotate the last assistant message with a `data-work-timing` part so the
 * work-phase duration survives a reload. No-op when the turn did no tool/
 * reasoning work, or when already annotated. Returns a new array (never mutates
 * the SDK's message objects).
 */
function withWorkTiming(messages: UIMessage[], ms: number | null): UIMessage[] {
  if (ms == null) return messages;
  let idx = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === "assistant") {
      idx = i;
      break;
    }
  }
  if (idx < 0) return messages;
  const parts = (messages[idx].parts ?? []) as { type: string }[];
  if (!parts.some(isWorkPart) || parts.some((p) => p.type === WORK_TIMING_PART)) {
    return messages;
  }
  const seconds = Math.max(0, Math.round(ms / 1000));
  const next = messages.slice();
  next[idx] = {
    ...messages[idx],
    parts: [...parts, { type: WORK_TIMING_PART, data: { seconds } }],
  } as UIMessage;
  return next;
}

/** Append a `data-message-time` part to a message, unless it already has one.
 * Returns a new message object (never mutates the SDK's). */
function stampTime(msg: UIMessage, ms: number): UIMessage {
  const parts = (msg.parts ?? []) as { type: string }[];
  if (parts.some((p) => p.type === MESSAGE_TIME_PART)) return msg;
  return {
    ...msg,
    parts: [...parts, { type: MESSAGE_TIME_PART, data: { ms } }],
  } as UIMessage;
}

/**
 * Stamp the turn's user + assistant messages with creation times (the user with
 * the send time, the assistant with the finish time), skipping any already
 * stamped. Returns a new array; only the changed entries are cloned.
 */
function withMessageTimes(
  messages: UIMessage[],
  userMs: number | null,
  assistantMs: number,
): UIMessage[] {
  let lastUser = -1;
  let lastAssistant = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (lastAssistant < 0 && messages[i].role === "assistant") lastAssistant = i;
    if (lastUser < 0 && messages[i].role === "user") lastUser = i;
    if (lastUser >= 0 && lastAssistant >= 0) break;
  }
  const next = messages.slice();
  if (lastUser >= 0 && userMs != null) next[lastUser] = stampTime(next[lastUser], userMs);
  if (lastAssistant >= 0) next[lastAssistant] = stampTime(next[lastAssistant], assistantMs);
  return next;
}

// The endpoint is fixed; filters are attached per-send via the request body, so
// one stateless transport instance is shared across every chat surface.
// Resuming asks for the thread's running answer; `have` (messages already on
// screen) lets the server reply 204 when the answer is already among them.
const transport = new DefaultChatTransport({
  api: "/api/chat",
  prepareReconnectToStreamRequest: ({ api, id, body }) => ({
    api: `${api}/${encodeURIComponent(id)}/stream?have=${Number(body?.have ?? 0)}`,
  }),
});

export type UseAgentChatOptions = {
  /** Stable chat/thread id (continuable threads persist under this id). */
  id?: string;
  /** Messages to seed the conversation with when reopening a saved thread. */
  initialMessages?: UIMessage[];
  /**
   * Called when an assistant turn's stream ends, with the full message list.
   * `complete` is false when it was stopped, dropped or errored: the live list
   * then lacks the parts the server wrote after that point.
   */
  onFinish?: (messages: UIMessage[], complete: boolean) => void;
  /**
   * Pick up a turn still answering on the server when the conversation mounts
   * (reopened or reloaded mid-answer). Threads only — the Reader chat has none.
   */
  resume?: boolean;
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

  // Work-phase timing: stamped at send, frozen when the answer text first
  // appears (see the effect below), and attached to the persisted message.
  const turnStartRef = useRef<number | null>(null);
  const workMsRef = useRef<number | null>(null);
  // Holds the SDK's `setMessages` so `onFinish` (defined before the hook
  // returns) can write the stamped messages back into the live conversation.
  const setMessagesRef = useRef<((m: UIMessage[]) => void) | null>(null);

  const chat = useChat({
    transport,
    id: opts?.id,
    messages: opts?.initialMessages,
    // Always defined: even without a callback (the ephemeral Reader chat) we
    // still stamp message times so they render live. A thread's turn already
    // streams its own timing parts from the server, so only the user's send
    // time is added there. Aborted/errored turns are left untouched.
    onFinish: ({ messages, isAbort, isDisconnect, isError }) => {
      if (isAbort || isDisconnect || isError) {
        onFinish?.(messages, false);
        return;
      }
      const stamped = withMessageTimes(
        withWorkTiming(messages, workMsRef.current),
        turnStartRef.current,
        Date.now(),
      );
      setMessagesRef.current?.(stamped);
      onFinish?.(stamped, true);
    },
  });
  const { messages, sendMessage, regenerate, status, setMessages } = chat;
  useEffect(() => {
    setMessagesRef.current = setMessages as (m: UIMessage[]) => void;
  }, [setMessages]);

  // Resume once per mount (the ref also absorbs StrictMode's double effect).
  // Not useChat's `resume` flag: it can't tell the server how many messages
  // are already on screen. A thread with no messages has nothing running (a
  // turn saves its question before answering), so a new chat skips the call.
  const resumedRef = useRef(false);
  const resumeStream = chat.resumeStream;
  const seededCount = opts?.initialMessages?.length ?? 0;
  const resume = !!opts?.resume;
  useEffect(() => {
    if (!resume || resumedRef.current || seededCount === 0) return;
    resumedRef.current = true;
    void resumeStream({ body: { have: seededCount } });
  }, [resume, resumeStream, seededCount]);

  const isStreaming = status === "submitted" || status === "streaming";

  // Refs mirroring per-render values, so the action callbacks below can be
  // referentially STABLE (empty deps). Without this they'd be recreated on every
  // streamed token (they read `messages`/`isStreaming`/the `chat` object), which
  // would defeat the memoized <Message> rows that receive them as props and force
  // the whole thread to re-render — and re-parse its markdown — per token. The
  // refs are synced in an effect (post-commit) and read only at event time, so
  // the callbacks always see the latest committed values.
  const messagesRef = useRef(messages);
  const isStreamingRef = useRef(isStreaming);
  const sdkRef = useRef({ sendMessage, regenerate, setMessages, stop: chat.stop });
  useEffect(() => {
    messagesRef.current = messages;
    isStreamingRef.current = isStreaming;
    sdkRef.current = { sendMessage, regenerate, setMessages, stop: chat.stop };
  });

  // Freeze the work-phase duration the moment the assistant's first answer text
  // streams in (mirrors when the `WorkTrace` live timer stops). Captured once
  // per turn; reset at send/regenerate.
  useEffect(() => {
    if (!isStreaming || turnStartRef.current == null || workMsRef.current != null) return;
    const last = messages[messages.length - 1];
    if (last?.role !== "assistant") return;
    const hasText = (last.parts ?? []).some(
      (p) => (p as { type: string; text?: string }).type === "text" &&
        !!(p as { text?: string }).text,
    );
    if (hasText) workMsRef.current = Date.now() - turnStartRef.current;
  }, [messages, isStreaming]);

  const send = useCallback((text: string, filters?: ChatFilters) => {
    const q = text.trim();
    if (!q || isStreamingRef.current) return;
    const now = Date.now();
    turnStartRef.current = now;
    workMsRef.current = null;
    void sdkRef.current.sendMessage({ text: q }, { body: requestBody(filters, now) });
  }, []);

  const regenerateWith = useCallback((filters?: ChatFilters) => {
    if (isStreamingRef.current) return;
    const now = Date.now();
    turnStartRef.current = now;
    workMsRef.current = null;
    void sdkRef.current.regenerate({ body: requestBody(filters, now) });
  }, []);

  /**
   * Edit a prior user turn and re-run from there: drop that message and every
   * turn after it, then send the new text — so the assistant answers the edited
   * question with no stale follow-ups left dangling. No-op while streaming or if
   * the id isn't a current message.
   */
  const editAndResend = useCallback(
    (messageId: string, text: string, filters?: ChatFilters) => {
      const q = text.trim();
      if (!q || isStreamingRef.current) return;
      const msgs = messagesRef.current;
      const idx = msgs.findIndex((m) => m.id === messageId);
      if (idx < 0) return;
      // setMessages and sendMessage both act on the same Chat instance, so the
      // truncation is in place before the new turn is appended.
      sdkRef.current.setMessages(msgs.slice(0, idx));
      const now = Date.now();
      turnStartRef.current = now;
      workMsRef.current = null;
      void sdkRef.current.sendMessage({ text: q }, { body: requestBody(filters, now) });
    },
    [],
  );

  const stop = useCallback(() => sdkRef.current.stop(), []);

  const reset = useCallback(() => {
    sdkRef.current.stop();
    sdkRef.current.setMessages([]);
  }, []);

  return {
    messages,
    status,
    isStreaming,
    error: chat.error,
    send,
    regenerate: regenerateWith,
    editAndResend,
    stop,
    reset,
  };
}

export type AgentChat = ReturnType<typeof useAgentChat>;
