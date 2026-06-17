import { useEffect, useState } from "react";
import { Command } from "cmdk";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Home,
  Library,
  Layers,
  MessageSquare,
  BarChart3,
  Plus,
  Search,
  CornerDownLeft,
} from "lucide-react";
import { getItems } from "@/lib/api/endpoints";
import { useUi } from "@/store/ui";
import { useDebounced } from "@/hooks/useDebounced";
import { StatusDot } from "@/components/common/StatusDot";

const ROUTES = [
  { to: "/", label: "Today", icon: Home },
  { to: "/feed", label: "Feed", icon: Layers },
  { to: "/library", label: "Library", icon: Library },
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/insights", label: "Insights", icon: BarChart3 },
];

export function CommandPalette() {
  const open = useUi((s) => s.paletteOpen);
  const setOpen = useUi((s) => s.setPaletteOpen);
  const openAdd = useUi((s) => s.openAdd);
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const debounced = useDebounced(query, 250);

  // Global ⌘K / Ctrl-K toggle.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(!useUi.getState().paletteOpen);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [setOpen]);

  const results = useQuery({
    queryKey: ["palette-search", debounced],
    queryFn: () => getItems({ search: debounced, per_page: 6, sort: "newest" }),
    enabled: open && debounced.trim().length >= 2,
    staleTime: 15_000,
  });

  const go = (fn: () => void) => {
    setOpen(false);
    setQuery("");
    fn();
  };

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Command palette"
      shouldFilter={false}
      className="fixed left-1/2 top-[20%] z-50 w-full max-w-xl -translate-x-1/2 overflow-hidden rounded-[14px] border border-border-strong bg-surface-2 shadow-2xl shadow-black/60 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
    >
      <div className="flex items-center gap-2 border-b border-border px-4">
        <Search className="size-4 text-fg-subtle" />
        <Command.Input
          autoFocus
          value={query}
          onValueChange={setQuery}
          placeholder="Search items, jump to a page, or take an action…"
          className="h-12 flex-1 bg-transparent text-sm text-fg outline-none placeholder:text-fg-subtle"
        />
      </div>

      <Command.List className="max-h-[60vh] overflow-y-auto p-2">
        <Command.Empty className="py-6 text-center text-sm text-fg-subtle">
          {debounced.trim().length >= 2 && results.isFetching
            ? "Searching…"
            : "No results."}
        </Command.Empty>

        {(results.data?.items.length ?? 0) > 0 && (
          <Command.Group
            heading="Items"
            className="[&_[cmdk-group-heading]]:eyebrow [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5"
          >
            {results.data!.items.map((item) => (
              <Command.Item
                key={item.id}
                value={`item-${item.id}`}
                onSelect={() => go(() => navigate(`/library/${item.id}`))}
                className="flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-2 text-sm text-fg-muted aria-selected:bg-surface aria-selected:text-fg"
              >
                <StatusDot status={item.status} />
                <span className="flex-1 truncate">{item.title ?? "Untitled"}</span>
                <span className="font-mono text-[11px] text-fg-subtle">
                  {item.channel ?? item.author ?? ""}
                </span>
              </Command.Item>
            ))}
          </Command.Group>
        )}

        {query.trim().length >= 2 && (
          <Command.Item
            value="ask-query"
            onSelect={() =>
              go(() => navigate(`/chat?q=${encodeURIComponent(query.trim())}`))
            }
            className="flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-2 text-sm text-fg-muted aria-selected:bg-surface aria-selected:text-fg"
          >
            <MessageSquare className="size-4" />
            <span className="flex-1">
              Ask: <span className="text-fg">“{query.trim()}”</span>
            </span>
            <CornerDownLeft className="size-3.5 text-fg-subtle" />
          </Command.Item>
        )}

        <Command.Group
          heading="Go to"
          className="[&_[cmdk-group-heading]]:eyebrow [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5"
        >
          {ROUTES.map((r) => (
            <Command.Item
              key={r.to}
              value={`goto ${r.label}`}
              onSelect={() => go(() => navigate(r.to))}
              className="flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-2 text-sm text-fg-muted aria-selected:bg-surface aria-selected:text-fg"
            >
              <r.icon className="size-4" />
              {r.label}
            </Command.Item>
          ))}
        </Command.Group>

        <Command.Group
          heading="Actions"
          className="[&_[cmdk-group-heading]]:eyebrow [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5"
        >
          <Command.Item
            value="add source"
            onSelect={() => go(() => openAdd())}
            className="flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-2 text-sm text-fg-muted aria-selected:bg-surface aria-selected:text-fg"
          >
            <Plus className="size-4" />
            Add source
          </Command.Item>
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  );
}
