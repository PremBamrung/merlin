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
    staleTime: 30_000,
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
