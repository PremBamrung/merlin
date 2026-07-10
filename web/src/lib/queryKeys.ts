import type { FeedFilter, ItemQuery } from "./api/endpoints";

const hasFeedFilter = (f?: FeedFilter) => !!(f?.topics?.length || f?.tags?.length);

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
  // Filter-aware: switching topic/tag filter yields a new key (fresh queue),
  // while within a filter the staleTime:Infinity swipe-back behaviour holds.
  // Invalidation by the bare ["feed"] prefix still matches every filtered key.
  feed: (f?: FeedFilter) =>
    hasFeedFilter(f) ? (["feed", f] as const) : (["feed"] as const),
  topics: () => ["topics"] as const,
  uncategorisedCount: () => ["uncategorised-count"] as const,
  proposals: () => ["topic-proposals"] as const,
  unreadCount: () => ["unread-count"] as const,
  insights: (k: string) => ["insights", k] as const,
  health: () => ["health"] as const,
  // Chat history (continuable threads): the sidebar list + one opened thread.
  chatThreads: () => ["chat-threads"] as const,
  chatThread: (id: string) => ["chat-thread", id] as const,
};
