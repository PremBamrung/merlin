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
  insights: (k: string) => ["insights", k] as const,
  health: () => ["health"] as const,
};
