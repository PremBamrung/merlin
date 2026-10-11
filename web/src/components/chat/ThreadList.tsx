import { useCallback, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, MoreHorizontal, Pencil, Pin, PinOff, Plus, Search, Trash2 } from "lucide-react";
import {
  deleteChatThread,
  useChatThreads,
  useRenameThread,
  type ChatThreadSummary,
} from "@/hooks/useChatThreads";
import { useUi } from "@/store/ui";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Kbd, PanelSection } from "@/components/layout/PanelParts";
import { toast } from "@/components/ui/toaster";
import { keys } from "@/lib/queryKeys";
import { relDate } from "@/lib/format";
import { cn } from "@/lib/utils";

// Date buckets, in display order. Threads arrive newest-first (the API orders
// by updated_at desc), so iterating in order keeps each bucket sorted.
const BUCKETS = ["Today", "Yesterday", "Previous 7 Days", "Older"] as const;

function bucketOf(iso: string | null): (typeof BUCKETS)[number] {
  if (!iso) return "Older";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return "Older";
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const days = Math.round(
    (startOfDay(new Date()).getTime() - startOfDay(dt).getTime()) / 86_400_000,
  );
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return "Previous 7 Days";
  return "Older";
}

/** The Chat place's context panel: new chat, a filter over titles, then the
 *  threads grouped Pinned / Today / Yesterday / 7 days / Older. */
export function ThreadList({
  activeId,
  onSelect,
  onNew,
}: {
  activeId: string;
  onSelect: (id: string) => void;
  onNew: () => void;
}) {
  const { data: threads, isLoading } = useChatThreads();
  const qc = useQueryClient();
  const pinnedThreads = useUi((s) => s.pinnedThreads);
  const togglePin = useUi((s) => s.togglePin);
  const pinnedSet = useMemo(() => new Set(pinnedThreads), [pinnedThreads]);
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const isMac = navigator.platform.toLowerCase().includes("mac");

  // Optimistic delete with an undo window: drop the row immediately, defer the
  // real DELETE, and let Undo cancel it (the thread was never actually removed,
  // so undo just re-fetches). No backend "restore" needed. Timers outlive an
  // unmount on purpose, so the delete still fires if the user navigates away.
  const pendingDeletes = useRef<Map<string, number>>(new Map());
  const deleteThread = useCallback(
    (id: string) => {
      qc.setQueryData<ChatThreadSummary[]>(keys.chatThreads(), (cur) =>
        (cur ?? []).filter((t) => t.id !== id),
      );
      if (id === activeId) onNew();
      const timer = window.setTimeout(() => {
        pendingDeletes.current.delete(id);
        deleteChatThread(id)
          .catch(() => {})
          .finally(() => qc.invalidateQueries({ queryKey: keys.chatThreads() }));
      }, 4500);
      pendingDeletes.current.set(id, timer);
      toast("Conversation deleted", {
        duration: 4000,
        action: {
          label: "Undo",
          onClick: () => {
            const t = pendingDeletes.current.get(id);
            if (t) {
              window.clearTimeout(t);
              pendingDeletes.current.delete(id);
            }
            qc.invalidateQueries({ queryKey: keys.chatThreads() });
          },
        },
      });
    },
    [qc, activeId, onNew],
  );

  // Client-side filter over title + first-message preview (the only text the
  // list endpoint returns; deep message content isn't searched).
  const filtered = useMemo(() => {
    if (!threads) return [];
    if (!q) return threads;
    return threads.filter(
      (t) =>
        (t.title ?? "").toLowerCase().includes(q) ||
        (t.preview ?? "").toLowerCase().includes(q),
    );
  }, [threads, q]);

  // Grouped by date bucket, with pinned threads lifted into a "Pinned" group at
  // the top — but a search shows a flat result list instead.
  const groups = useMemo(() => {
    if (q) return [];
    const out: (readonly [string, ChatThreadSummary[]])[] = [];
    const pinned = filtered.filter((t) => pinnedSet.has(t.id));
    if (pinned.length) out.push(["Pinned", pinned] as const);
    const map = new Map<string, ChatThreadSummary[]>();
    for (const t of filtered) {
      if (pinnedSet.has(t.id)) continue;
      const b = bucketOf(t.updated_at);
      (map.get(b) ?? map.set(b, []).get(b)!).push(t);
    }
    for (const b of BUCKETS) if (map.has(b)) out.push([b, map.get(b)!] as const);
    return out;
  }, [filtered, q, pinnedSet]);

  const row = (t: ChatThreadSummary) => (
    <ThreadRow
      key={t.id}
      thread={t}
      active={t.id === activeId}
      pinned={pinnedSet.has(t.id)}
      onSelect={() => onSelect(t.id)}
      onPin={() => togglePin(t.id)}
      onDelete={() => deleteThread(t.id)}
    />
  );

  return (
    <div>
      <div className="grid gap-1 pb-1.5">
        <Button
          variant="secondary"
          className="h-[38px] w-full justify-start border-border bg-surface text-[14px]"
          onClick={onNew}
        >
          <Plus className="size-4" /> New chat
          <Kbd className="ml-auto">{isMac ? "⌘ ⇧ O" : "Ctrl ⇧ O"}</Kbd>
        </Button>
        <label className="flex h-9 items-center gap-[9px] rounded-md border border-border px-2.5 text-fg-subtle transition-colors focus-within:border-ui-focus-border">
          <Search className="size-4 shrink-0" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search chats"
            aria-label="Search chats"
            className="min-w-0 flex-1 bg-transparent text-[16px] text-fg outline-none placeholder:text-fg-subtle md:text-[14px]"
          />
        </label>
      </div>

      {isLoading ? (
        <div className="space-y-2 px-1 py-3">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      ) : !threads || threads.length === 0 ? (
        <p className="px-2 py-6 text-center text-[13px] text-fg-subtle">
          No saved conversations yet.
        </p>
      ) : filtered.length === 0 ? (
        <p className="px-2 py-6 text-center text-[13px] text-fg-subtle">
          No conversations match “{query.trim()}”.
        </p>
      ) : q ? (
        <div className="space-y-px pt-2">{filtered.map(row)}</div>
      ) : (
        groups.map(([label, items]) => (
          <PanelSection key={label} title={label}>
            {items.map(row)}
          </PanelSection>
        ))
      )}
    </div>
  );
}

function ThreadRow({
  thread,
  active,
  pinned,
  onSelect,
  onPin,
  onDelete,
}: {
  thread: ChatThreadSummary;
  active: boolean;
  pinned: boolean;
  onSelect: () => void;
  onPin: () => void;
  onDelete: () => void;
}) {
  const rename = useRenameThread();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  const label = thread.title || thread.preview || "New conversation";

  const commitRename = () => {
    const title = draft.trim();
    if (title && title !== thread.title) rename.mutate({ id: thread.id, title });
    setEditing(false);
  };

  if (editing) {
    return (
      <div className="flex items-center gap-1 px-1 py-0.5">
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commitRename();
            if (e.key === "Escape") setEditing(false);
          }}
          onBlur={commitRename}
          className="min-w-0 flex-1 rounded-md border border-border-strong bg-surface px-2 py-1 text-[16px] outline-none md:text-[14px]"
        />
        <Button variant="ghost" size="icon" className="size-7" onClick={commitRename}>
          <Check className="size-3.5" />
        </Button>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "group flex h-[34px] items-center gap-1 rounded-md pl-2.5 pr-1 transition-colors",
        active
          ? "bg-ui-selected-bg text-fg shadow-[inset_2px_0_0_var(--color-ui-selected-bar)]"
          : "text-fg-muted hover:bg-surface hover:text-fg",
      )}
    >
      <button
        onClick={onSelect}
        className="flex h-full min-w-0 flex-1 items-center gap-2 text-left"
        title={`${label} · ${relDate(thread.updated_at)}${thread.message_count ? ` · ${thread.message_count} messages` : ""}`}
        aria-current={active ? "page" : undefined}
      >
        <span className="min-w-0 flex-1 truncate text-[14px]">{label}</span>
        {pinned && <Pin className="size-3 shrink-0 text-fg-subtle" />}
      </button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            className="shrink-0 rounded-[6px] p-1 text-fg-subtle opacity-0 transition-opacity hover:text-fg focus-visible:opacity-100 group-hover:opacity-100 data-[state=open]:opacity-100 pointer-coarse:opacity-100"
            aria-label="Conversation options"
            onClick={(e) => e.stopPropagation()}
          >
            <MoreHorizontal className="size-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={onPin}>
            {pinned ? <PinOff className="size-3.5" /> : <Pin className="size-3.5" />}
            {pinned ? "Unpin" : "Pin"}
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => {
              setDraft(thread.title || "");
              setEditing(true);
            }}
          >
            <Pencil className="size-3.5" /> Rename
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={onDelete} className="text-fail focus:text-fail">
            <Trash2 className="size-3.5" /> Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
