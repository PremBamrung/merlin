import { useCallback, useRef, useState } from "react";
import { chatStream, type Citation } from "@/lib/api/client";
import type { ChatFilters } from "@/lib/api/endpoints";

export type ChatTurn = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  streaming?: boolean;
  error?: string;
};

let _id = 0;
const nextId = () => `m${++_id}`;

/**
 * Client-side chat session over the `/api/chat` SSE stream. History lives here
 * and is replayed to the backend each turn. Disable the composer while
 * `isStreaming`; a new send aborts the in-flight stream.
 */
export function useChatStream() {
  const [messages, setMessages] = useState<ChatTurn[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const ctrl = useRef<AbortController | null>(null);
  const filtersRef = useRef<ChatFilters | undefined>(undefined);

  const patch = (id: string, fn: (t: ChatTurn) => ChatTurn) =>
    setMessages((cur) => cur.map((m) => (m.id === id ? fn(m) : m)));

  const run = useCallback(
    async (question: string, history: ChatTurn[], filters?: ChatFilters) => {
      ctrl.current?.abort();
      const ac = new AbortController();
      ctrl.current = ac;
      setIsStreaming(true);

      const assistantId = nextId();
      setMessages([
        ...history,
        { id: nextId(), role: "user", content: question },
        { id: assistantId, role: "assistant", content: "", streaming: true },
      ]);

      try {
        const stream = chatStream(
          {
            question,
            history: history.map((m) => ({ role: m.role, content: m.content })),
            filters: filters ?? null,
          },
          ac.signal,
        );
        for await (const frame of stream) {
          if (frame.type === "citations") {
            patch(assistantId, (t) => ({ ...t, citations: frame.citations }));
          } else if (frame.type === "token") {
            patch(assistantId, (t) => ({ ...t, content: t.content + frame.text }));
          } else if (frame.type === "done") {
            patch(assistantId, (t) => ({ ...t, streaming: false }));
          } else if (frame.type === "error") {
            patch(assistantId, (t) => ({
              ...t,
              streaming: false,
              error: frame.error.message,
            }));
          }
        }
      } catch (e) {
        if (!ac.signal.aborted) {
          patch(assistantId, (t) => ({
            ...t,
            streaming: false,
            error: e instanceof Error ? e.message : "Stream failed.",
          }));
        }
      } finally {
        if (ctrl.current === ac) {
          patch(assistantId, (t) => ({ ...t, streaming: false }));
          setIsStreaming(false);
        }
      }
    },
    [],
  );

  const send = useCallback(
    (question: string, filters?: ChatFilters) => {
      const q = question.trim();
      if (!q || isStreaming) return;
      filtersRef.current = filters;
      setMessages((cur) => {
        void run(q, cur, filters);
        return cur;
      });
    },
    [isStreaming, run],
  );

  /** Re-run the last user turn, discarding the previous assistant answer. */
  const regenerate = useCallback(() => {
    if (isStreaming) return;
    setMessages((cur) => {
      const lastUser = [...cur].reverse().find((m) => m.role === "user");
      if (!lastUser) return cur;
      const idx = cur.findIndex((m) => m.id === lastUser.id);
      const history = cur.slice(0, idx);
      void run(lastUser.content, history, filtersRef.current);
      return cur;
    });
  }, [isStreaming, run]);

  const stop = useCallback(() => {
    ctrl.current?.abort();
    setIsStreaming(false);
  }, []);

  const reset = useCallback(() => {
    ctrl.current?.abort();
    setMessages([]);
    setIsStreaming(false);
  }, []);

  return { messages, isStreaming, send, regenerate, stop, reset };
}
