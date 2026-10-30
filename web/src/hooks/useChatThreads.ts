import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, client } from "@/lib/api/client";
import { keys } from "@/lib/queryKeys";

/**
 * Chat-history (continuable threads). Like the rest of the chat surface, these
 * types live with the hook rather than the generated OpenAPI client — the chat
 * path speaks the Vercel AI SDK protocol, and a message's `parts` are stored
 * verbatim as opaque `UIMessage` parts.
 */
export type ChatThreadSummary = {
  id: string;
  title: string | null;
  created_at: string | null;
  updated_at: string | null;
  message_count: number;
  preview: string | null;
  /** An answer is still running on the server. */
  active: boolean;
};

export type StoredMessage = {
  id?: string;
  role: string;
  parts: unknown[];
};

export type ChatThreadDetail = {
  id: string;
  title: string | null;
  created_at: string | null;
  updated_at: string | null;
  messages: StoredMessage[];
};

// --- endpoints -------------------------------------------------------------- //

const listChatThreads = () =>
  client.get<ChatThreadSummary[]>("/api/chat/threads");

const getChatThread = (id: string) =>
  client.get<ChatThreadDetail>(`/api/chat/threads/${id}`);

/** Cancel the thread's running answer on the server. Resolves once the
 * partial answer is saved. (The server saves every turn itself.) */
export const stopChatTurn = (id: string) =>
  client.post<void>(`/api/chat/${encodeURIComponent(id)}/stop`);

const renameChatThread = (id: string, title: string) =>
  client.patch<{ id: string; title: string | null }>(
    `/api/chat/threads/${id}`,
    { title },
  );

export const deleteChatThread = (id: string) =>
  client.delete<void>(`/api/chat/threads/${id}`);

// --- hooks ------------------------------------------------------------------ //

/** The thread sidebar list, newest-first (server-ordered by updated_at).
 * Polls while any thread is answering, so its dot clears when the answer
 * lands even if nobody is watching that thread. */
export function useChatThreads() {
  return useQuery({
    queryKey: keys.chatThreads(),
    queryFn: listChatThreads,
    staleTime: 10_000,
    refetchInterval: (q) => (q.state.data?.some((t) => t.active) ? 3_000 : false),
  });
}

/**
 * One thread's stored messages, for seeding `useChat` on open. A brand-new
 * (not-yet-persisted) thread id 404s — that's expected, so we resolve it to an
 * empty thread rather than an error and never retry.
 */
export function useChatThread(id: string) {
  return useQuery({
    queryKey: keys.chatThread(id),
    queryFn: async (): Promise<ChatThreadDetail> => {
      try {
        return await getChatThread(id);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
          return { id, title: null, created_at: null, updated_at: null, messages: [] };
        }
        throw e;
      }
    },
    retry: false,
    staleTime: Infinity, // seeded once into useChat; never refetch mid-thread
  });
}

export function useRenameThread() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      renameChatThread(id, title),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.chatThreads() }),
  });
}

export function useDeleteThread() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteChatThread(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.chatThreads() }),
  });
}
