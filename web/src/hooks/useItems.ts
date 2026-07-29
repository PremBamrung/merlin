import {
  useQuery,
  useMutation,
  useQueryClient,
  keepPreviousData,
} from "@tanstack/react-query";
import {
  getItems,
  getItem,
  updateItem,
  deleteItem,
  clearSummary,
  type ItemQuery,
  type Item,
  type ItemList,
  type ListItem,
} from "@/lib/api/endpoints";
import type { components } from "@/lib/api/schema";
import { keys } from "@/lib/queryKeys";
import { toast } from "@/components/ui/toaster";

/** Paginated/filtered list. keepPreviousData avoids a flash on page/filter change. */
export function useItems(query: ItemQuery) {
  return useQuery({
    queryKey: keys.items(query),
    queryFn: () => getItems(query),
    placeholderData: keepPreviousData,
  });
}

/** Item detail (includes raw_content). */
export function useItem(id: string | undefined) {
  return useQuery({
    queryKey: keys.item(id ?? ""),
    queryFn: () => getItem(id!),
    enabled: !!id,
  });
}

/**
 * Warm an item's detail into the cache before it's asked for — called on card
 * hover/focus, so the Reader's shared-element morph lands on real content
 * instead of a skeleton. A no-op once the item is cached and fresh.
 */
export function usePrefetchItem() {
  const qc = useQueryClient();
  return (id: string) =>
    qc.prefetchQuery({
      queryKey: keys.item(id),
      queryFn: () => getItem(id),
    });
}

/**
 * Prev/next neighbours of an item, read from whichever Library list page is
 * already cached (the grid the user came from). No extra request: if the item
 * isn't in a cached page, both are null and the Reader simply hides the arrows.
 */
export function useAdjacentItems(id: string): {
  prev: ListItem | null;
  next: ListItem | null;
} {
  const qc = useQueryClient();
  const lists = qc.getQueriesData<ItemList>({ queryKey: keys.items() });
  for (const [, data] of lists) {
    const items = data?.items;
    if (!items) continue;
    const idx = items.findIndex((it) => it.id === id);
    if (idx === -1) continue;
    return {
      prev: idx > 0 ? items[idx - 1] : null,
      next: idx < items.length - 1 ? items[idx + 1] : null,
    };
  }
  return { prev: null, next: null };
}

/** Optimistic PATCH for tags/title (§5). Rolls back on error. */
export function useUpdateItem(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: components["schemas"]["UpdateItemRequest"]) =>
      updateItem(id, body),
    onMutate: async (next) => {
      await qc.cancelQueries({ queryKey: keys.item(id) });
      const prev = qc.getQueryData<Item>(keys.item(id));
      if (prev) qc.setQueryData<Item>(keys.item(id), { ...prev, ...next });
      return { prev };
    },
    onError: (err: Error, _next, ctx) => {
      if (ctx?.prev) qc.setQueryData(keys.item(id), ctx.prev);
      toast.error("Couldn't save changes", { description: err.message });
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: keys.item(id) });
      qc.invalidateQueries({ queryKey: keys.items() });
      qc.invalidateQueries({ queryKey: keys.tags() });
    },
  });
}

export function useDeleteItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteItem(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.items() });
      toast.success("Item deleted");
    },
    onError: (err: Error) => toast.error("Couldn't delete", { description: err.message }),
  });
}

export function useClearSummary(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => clearSummary(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.item(id) });
      qc.invalidateQueries({ queryKey: keys.items() });
      toast.success("Summary cleared");
    },
    onError: (err: Error) =>
      toast.error("Couldn't clear summary", { description: err.message }),
  });
}
