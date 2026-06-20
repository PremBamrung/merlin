import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
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

/** A consolidated citation, emitted by the server as a `data-citations` part. */
export type Citation = {
  item_id: string;
  title: string;
  source_type: string;
  snippet: string;
  score: number;
};

// The endpoint is fixed; filters are attached per-send via the request body, so
// one stateless transport instance is shared across every chat surface.
const transport = new DefaultChatTransport({ api: "/api/chat" });

/**
 * Thin wrapper over the Vercel AI SDK `useChat`. The SDK owns the streaming
 * message-parts protocol (text / tool calls / reasoning / data parts), framing,
 * abort, and incremental rendering; we add filter injection and a few ergonomic
 * helpers. History is in-memory and cleared on reload (ephemeral, v1).
 */
export function useAgentChat() {
  const chat = useChat({ transport });
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
