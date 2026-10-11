import { useState } from "react";
import { Archive, Check, GitMerge, Pencil, Plus, X } from "lucide-react";
import {
  useCreateTopic,
  useDeleteTopic,
  usePatchTopic,
  type TopicItem,
} from "@/hooks/useTopics";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { RescanButton } from "./ConfirmButtons";
import { cn } from "@/lib/utils";

// --------------------------------------------------------------------------- //
// Manage: create + per-topic row
// --------------------------------------------------------------------------- //

export function CreateTopicRow() {
  const create = useCreateTopic();
  const [label, setLabel] = useState("");
  const submit = () => {
    const l = label.trim();
    if (!l) return;
    create.mutate({ label: l }, { onSuccess: () => setLabel("") });
  };
  return (
    <div className="flex items-center gap-2">
      <Input
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        placeholder="New topic label…"
        className="max-w-[280px]"
      />
      <Button size="sm" variant="secondary" onClick={submit} disabled={!label.trim() || create.isPending}>
        <Plus className="size-3.5" /> Add
      </Button>
    </div>
  );
}

export function TopicRow({
  topic,
  all,
  busy,
  onRescan,
}: {
  topic: TopicItem;
  all: TopicItem[];
  busy: boolean;
  onRescan: (topic: TopicItem) => void;
}) {
  const patch = usePatchTopic();
  const del = useDeleteTopic();
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(topic.label);
  const others = all.filter((t) => t.id !== topic.id);

  const saveRename = () => {
    const l = label.trim();
    if (!l || l === topic.label) return setEditing(false);
    patch.mutate({ id: topic.id, body: { label: l } }, { onSuccess: () => setEditing(false) });
  };

  return (
    <li className="flex items-center gap-2 px-3 py-2">
      {editing ? (
        <>
          <Input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") saveRename();
              if (e.key === "Escape") { setLabel(topic.label); setEditing(false); }
            }}
            autoFocus
            className="h-8 max-w-[220px]"
          />
          <Button size="icon-sm" variant="ghost" onClick={saveRename} aria-label="Save">
            <Check className="size-4" />
          </Button>
          <Button
            size="icon-sm"
            variant="ghost"
            onClick={() => { setLabel(topic.label); setEditing(false); }}
            aria-label="Cancel"
          >
            <X className="size-4" />
          </Button>
        </>
      ) : (
        <>
          <span className="font-medium">{topic.label}</span>
          <span className="font-mono text-[11px] tabular-nums text-fg-subtle">
            {topic.count}
          </span>
          {topic.origin === "seed" && (
            <span className="rounded-full bg-surface-2 px-1.5 py-0.5 text-[10px] text-fg-subtle">
              seed
            </span>
          )}
          <div className="ml-auto flex items-center gap-0.5">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button size="icon-sm" variant="ghost" onClick={() => setEditing(true)} aria-label="Rename">
                  <Pencil className="size-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Rename topic</TooltipContent>
            </Tooltip>
            <RescanButton
              topic={topic}
              disabled={busy || topic.count === 0}
              onConfirm={() => onRescan(topic)}
            />
            {others.length > 0 && (
              <DropdownMenu>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <DropdownMenuTrigger asChild>
                      <Button size="icon-sm" variant="ghost" aria-label="Merge into">
                        <GitMerge className="size-3.5" />
                      </Button>
                    </DropdownMenuTrigger>
                  </TooltipTrigger>
                  <TooltipContent>Merge into another topic</TooltipContent>
                </Tooltip>
                <DropdownMenuContent align="end">
                  {others.map((t) => (
                    <DropdownMenuItem
                      key={t.id}
                      onSelect={() =>
                        patch.mutate({ id: topic.id, body: { merge_into: t.id } })
                      }
                    >
                      Merge into “{t.label}”
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="icon-sm"
                  variant="ghost"
                  onDoubleClick={() => patch.mutate({ id: topic.id, body: { archive: true } })}
                  aria-label="Archive topic (double-click to confirm)"
                >
                  <Archive className="size-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Archive topic (double-click) — hides it, keeps its items</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="icon-sm"
                  variant="ghost"
                  onDoubleClick={() => del.mutate(topic.id)}
                  aria-label="Delete topic (double-click to confirm)"
                  className={cn("text-fg-subtle hover:text-fail")}
                >
                  <X className="size-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Delete topic (double-click) — unassigns its items</TooltipContent>
            </Tooltip>
          </div>
        </>
      )}
    </li>
  );
}
