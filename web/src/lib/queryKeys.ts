import type { ItemQuery } from "./api/endpoints";

/** Central query-key factory so invalidation targets the narrowest scope (§3). */
export const keys = {
  items: (q?: ItemQuery) => (q ? (["items", q] as const) : (["items"] as const)),
  item: (id: string) => ["item", id] as const,
  tags: () => ["tags"] as const,
  sourceTypes: () => ["sourceTypes"] as const,
  tasks: () => ["tasks"] as const,
  task: (id: string) => ["task", id] as const,
  inbox: () => ["inbox"] as const,
  // The Feed queue is its own key (NOT keys.items) so marking-read never
  // invalidates/refetches it mid-session — cards stay put for swipe-back.
  feed: () => ["feed"] as const,
  unreadCount: () => ["unread-count"] as const,
  insights: (k: string) => ["insights", k] as const,
  health: () => ["health"] as const,
  // Chat history (continuable threads): the sidebar list + one opened thread.
  chatThreads: () => ["chat-threads"] as const,
  chatThread: (id: string) => ["chat-thread", id] as const,
};
