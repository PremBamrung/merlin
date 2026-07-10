import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
} from "@tanstack/react-query";
import {
  getItems,
  getUnreadCount,
  markAllRead,
  markRead,
  markUnread,
  saveItem,
  unsaveItem,
  type FeedFilter,
  type ItemList,
  type ListItem,
} from "@/lib/api/endpoints";
import { keys } from "@/lib/queryKeys";
import { toast } from "@/components/ui/toaster";

const PER_PAGE = 20;

/**
 * The unread reading queue, newest first. Its own query key (keys.feed) and
 * staleTime:Infinity mean marking-read never refetches it mid-session, so the
 * card list stays stable and you can swipe back to undo. A fresh visit
 * (remount) refetches and drops anything already read.
 */
export function useFeedQueue(filter?: FeedFilter) {
  return useInfiniteQuery({
    queryKey: keys.feed(filter),
    queryFn: ({ pageParam }) =>
      getItems({
        read: false,
        sort: "newest",
        per_page: PER_PAGE,
        page: pageParam,
        topics: filter?.topics,
        tags: filter?.tags,
      }),
    initialPageParam: 1,
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((n, p) => n + p.items.length, 0);
      return loaded < last.total ? pages.length + 1 : undefined;
    },
    staleTime: Infinity,
    gcTime: 0, // forget the snapshot once the Feed unmounts → fresh on return
  });
}

/** Unread queue size — drives the nav badge and the Feed progress count. */
export function useUnreadCount() {
  return useQuery({
    queryKey: keys.unreadCount(),
    queryFn: async () => (await getUnreadCount()).count,
    staleTime: 15_000,
  });
}

type CountCtx = { prev?: number };

/** Optimistically nudge the cached unread count by `delta`, returning the old value. */
function bumpUnread(
  qc: ReturnType<typeof useQueryClient>,
  delta: number,
): CountCtx {
  const prev = qc.getQueryData<number>(keys.unreadCount());
  if (prev !== undefined)
    qc.setQueryData(keys.unreadCount(), Math.max(0, prev + delta));
  return { prev };
}

function settleRead(qc: ReturnType<typeof useQueryClient>, item?: ListItem) {
  qc.invalidateQueries({ queryKey: keys.unreadCount() });
  qc.invalidateQueries({ queryKey: keys.items() }); // Library/Today reflect read state
  if (item)
    qc.setQueryData<ListItem>(keys.item(item.id), (old) =>
      old ? { ...old, read_at: item.read_at } : old,
    );
}

/** Mark read (advancing past a card). Optimistically decrements the count. */
export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => markRead(id),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: keys.unreadCount() });
      return bumpUnread(qc, -1);
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.prev !== undefined) qc.setQueryData(keys.unreadCount(), ctx.prev);
    },
    onSettled: (item) => settleRead(qc, item ?? undefined),
  });
}

/** Re-open a card (the Undo path). Optimistically increments the count. */
export function useMarkUnread() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => markUnread(id),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: keys.unreadCount() });
      return bumpUnread(qc, +1);
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.prev !== undefined) qc.setQueryData(keys.unreadCount(), ctx.prev);
    },
    onSettled: (item) => settleRead(qc, item ?? undefined),
  });
}

/** Patch one item across every cached feed page (any active filter). Targets
 *  the ["feed"] prefix via setQueriesData so it hits the filter-aware keys too. */
function patchFeedItem(
  qc: ReturnType<typeof useQueryClient>,
  id: string,
  patch: Partial<ListItem>,
) {
  qc.setQueriesData<InfiniteData<ItemList>>({ queryKey: keys.feed() }, (old) =>
    old
      ? {
          ...old,
          pages: old.pages.map((pg) => ({
            ...pg,
            items: pg.items.map((it) =>
              it.id === id ? { ...it, ...patch } : it,
            ),
          })),
        }
      : old,
  );
}

/** Mark the whole backlog read — clears the queue (and the one-time backfill). */
export function useMarkAllRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: markAllRead,
    onSuccess: ({ count }) => {
      qc.setQueryData(keys.unreadCount(), 0);
      qc.invalidateQueries({ queryKey: keys.feed() }); // refetch → empty queue
      qc.invalidateQueries({ queryKey: keys.items() });
      toast.success(
        count > 0 ? `Marked ${count} as read` : "Nothing left to read",
      );
    },
    onError: (err: Error) =>
      toast.error("Couldn't mark all read", { description: err.message }),
  });
}

/** Toggle the ★ bookmark. Optimistically flips saved_at in the feed snapshot. */
export function useToggleSaved() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, saved }: { id: string; saved: boolean }) =>
      saved ? saveItem(id) : unsaveItem(id),
    onMutate: ({ id, saved }) => {
      patchFeedItem(qc, id, { saved_at: saved ? new Date().toISOString() : null });
    },
    onError: (err: Error, { id, saved }) => {
      patchFeedItem(qc, id, { saved_at: saved ? null : new Date().toISOString() });
      toast.error("Couldn't update", { description: err.message });
    },
    onSettled: (item) => {
      qc.invalidateQueries({ queryKey: keys.items() });
      if (item)
        qc.setQueryData<ListItem>(keys.item(item.id), (old) =>
          old ? { ...old, saved_at: item.saved_at } : old,
        );
    },
  });
}
