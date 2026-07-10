import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Sparkles,
  Check,
  X,
  Pencil,
  Archive,
  GitMerge,
  Plus,
  Layers,
  RefreshCw,
  Tags as TagsIcon,
} from "lucide-react";
import {
  useAcceptProposal,
  useBackfill,
  useCreateTopic,
  useDeleteTopic,
  usePatchTopic,
  useProposals,
  useProposeTopics,
  useReclassifyAll,
  useReclassifyTopic,
  useRejectProposal,
  useTopics,
  useUncategorisedCount,
  type TopicItem,
} from "@/hooks/useTopics";
import { useCancelTask } from "@/hooks/useIngest";
import { getTask, type TopicProposal } from "@/lib/api/endpoints";
import { keys } from "@/lib/queryKeys";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { EmptyState } from "@/components/common/EmptyState";
import { toast } from "@/components/ui/toaster";
import { cn } from "@/lib/utils";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

export default function TopicsRoute() {
  const topics = useTopics("active");
  const proposals = useProposals();
  const uncategorised = useUncategorisedCount();
  const propose = useProposeTopics();
  const backfill = useBackfill();
  const reclassify = useReclassifyTopic();
  const reclassifyAll = useReclassifyAll();
  const cancel = useCancelTask();
  const qc = useQueryClient();

  // A single background task runs at a time (the two buttons are mutually
  // exclusive). Poll it until it settles, then refresh the lists. `kind` drives
  // the completion toast + progress copy; `running` is derived from live status,
  // so the effect never needs to write state.
  const [taskId, setTaskId] = useState<string | null>(null);
  const [kind, setKind] = useState<
    "discovery" | "backfill" | "rescan" | "rescan-all" | null
  >(null);
  // The topic being re-scanned, for the progress/toast copy.
  const [rescanLabel, setRescanLabel] = useState<string | null>(null);
  const task = useQuery({
    queryKey: keys.task(taskId ?? ""),
    queryFn: () => getTask(taskId!),
    enabled: !!taskId,
    refetchInterval: (q) =>
      TERMINAL.has(q.state.data?.status ?? "") ? false : 1500,
  });
  useEffect(() => {
    const status = task.data?.status;
    if (!status || !TERMINAL.has(status)) return;
    // React to the external task completing: refresh the lists (no setState).
    qc.invalidateQueries({ queryKey: keys.proposals() });
    qc.invalidateQueries({ queryKey: keys.uncategorisedCount() });
    qc.invalidateQueries({ queryKey: keys.topics() });
    qc.invalidateQueries({ queryKey: keys.items() });
    qc.invalidateQueries({ queryKey: keys.feed() });
    const noun =
      kind === "backfill"
        ? "Backfill"
        : kind === "rescan"
          ? "Re-scan"
          : kind === "rescan-all"
            ? "Full re-scan"
            : "Topic discovery";
    const wasCancelled = !!task.data?.result_data?.cancelled;
    if (status === "failed") toast.error(`${noun} failed`);
    else if (wasCancelled) toast.success(`${noun} stopped — kept the work done so far`);
    else toast.success(`${noun} complete`);
  }, [task.data?.status, task.data?.result_data, kind, qc]);

  const running = !!taskId && !TERMINAL.has(task.data?.status ?? "");
  const busy =
    running ||
    propose.isPending ||
    backfill.isPending ||
    reclassify.isPending ||
    reclassifyAll.isPending;
  // Cancel POST returns instantly ("cancelling"), but the task keeps running to
  // its next checkpoint — keep the button in "Stopping…" until it terminates.
  const stopping =
    cancel.isPending ||
    (cancel.isSuccess && cancel.variables === taskId && running);
  const startDiscovery = () =>
    propose.mutate(undefined, {
      onSuccess: (r) => {
        setKind("discovery");
        setTaskId(r.task_id);
      },
    });
  const startBackfill = () =>
    backfill.mutate(undefined, {
      onSuccess: (r) => {
        setKind("backfill");
        setTaskId(r.task_id);
      },
    });
  const startRescan = (topic: TopicItem) =>
    reclassify.mutate(topic.id, {
      onSuccess: (r) => {
        setKind("rescan");
        setRescanLabel(topic.label);
        setTaskId(r.task_id);
      },
    });
  const startRescanAll = () =>
    reclassifyAll.mutate(undefined, {
      onSuccess: (r) => {
        setKind("rescan-all");
        setTaskId(r.task_id);
      },
    });

  const pending = proposals.data ?? [];
  const uncat = uncategorised.data ?? 0;
  const hasTopics = (topics.data?.length ?? 0) > 0;
  // Upper-bound estimate of a full re-scan's LLM calls, for the confirm dialog:
  // every categorised item (topic counts over-count multi-topic items) + the
  // uncategorised pile. The task reports the exact count once it starts.
  const totalEstimate =
    (topics.data?.reduce((sum, t) => sum + t.count, 0) ?? 0) + uncat;

  return (
    <div className="mx-auto max-w-[900px] space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-semibold">Topics</h1>
          <p className="mt-1 text-[13px] text-fg-muted">
            Your navigation taxonomy — the buckets the Feed filters by.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ReclassifyAllButton
            total={totalEstimate}
            disabled={busy || !hasTopics}
            onConfirm={startRescanAll}
          />
          <BackfillButton
            uncat={uncat}
            disabled={busy || !hasTopics}
            onConfirm={startBackfill}
          />
          <Button size="sm" onClick={startDiscovery} disabled={busy}>
            <Sparkles className="size-4" />
            {running && kind === "discovery" ? "Finding topics…" : "Find topics"}
            {uncat > 0 && !running && (
              <span className="ml-1 font-mono text-[11px] tabular-nums opacity-80">
                {uncat}
              </span>
            )}
          </Button>
        </div>
      </div>

      {running && (
        <div className="flex items-center gap-3 rounded-lg border border-border bg-surface/40 p-4 text-[13px] text-fg-muted">
          <span className="flex-1">
            {task.data?.message ||
              (kind === "backfill"
                ? "Classifying uncategorised items…"
                : kind === "rescan"
                  ? `Re-scanning ${rescanLabel ?? "topic"}…`
                  : kind === "rescan-all"
                    ? "Re-scanning your whole library…"
                    : "Clustering uncategorised items…")}
            {typeof task.data?.progress === "number" && ` (${task.data.progress}%)`}
          </span>
          <Button
            size="sm"
            variant="ghost"
            disabled={stopping || !taskId}
            onClick={() => taskId && cancel.mutate(taskId)}
          >
            <X className="size-3.5" />
            {stopping ? "Stopping…" : "Cancel"}
          </Button>
        </div>
      )}

      {/* Review queue */}
      {pending.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-[15px] font-semibold">
            Proposed topics{" "}
            <span className="text-fg-subtle">({pending.length})</span>
          </h2>
          <div className="space-y-3">
            {pending.map((p) => (
              <ProposalCard key={p.id} proposal={p} topics={topics.data ?? []} />
            ))}
          </div>
        </section>
      )}

      {/* Manage taxonomy */}
      <section className="space-y-3">
        <h2 className="text-[15px] font-semibold">Manage</h2>
        <CreateTopicRow />
        {topics.isLoading ? null : (topics.data?.length ?? 0) === 0 ? (
          <EmptyState
            icon={TagsIcon}
            title="No topics yet"
            description={
              uncat > 0
                ? `You have ${uncat} uncategorised items. Add a few topics, or click "Find topics" to let the assistant propose some.`
                : "Add a topic to start organising your library."
            }
          />
        ) : (
          <ul className="divide-y divide-border rounded-lg border border-border">
            {topics.data!.map((t) => (
              <TopicRow
                key={t.id}
                topic={t}
                all={topics.data!}
                busy={busy}
                onRescan={startRescan}
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Backfill: fit uncategorised items to EXISTING topics (behind a cost confirm)
// --------------------------------------------------------------------------- //

function BackfillButton({
  uncat,
  disabled,
  onConfirm,
}: {
  uncat: number;
  disabled: boolean;
  onConfirm: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="secondary" disabled={disabled || uncat === 0}>
          <Layers className="size-4" />
          Classify {uncat} uncategorised
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Classify uncategorised items?</DialogTitle>
          <DialogDescription>
            This fits your {uncat} uncategorised item{uncat === 1 ? "" : "s"} to
            the topics you already have — one LLM call each (~{uncat} calls), which
            costs money. It never touches items you've assigned by hand. New topics
            aren't created here; use “Find topics” for that.
          </DialogDescription>
        </DialogHeader>
        <div className="mt-4 flex justify-end gap-2">
          <DialogClose asChild>
            <Button size="sm" variant="ghost">
              Cancel
            </Button>
          </DialogClose>
          <Button
            size="sm"
            onClick={() => {
              setOpen(false);
              onConfirm();
            }}
          >
            <Layers className="size-4" />
            Classify {uncat}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
// Full re-scan: re-decide the WHOLE library against the current taxonomy
// (behind a cost confirm — one LLM call per item across the whole corpus)
// --------------------------------------------------------------------------- //

function ReclassifyAllButton({
  total,
  disabled,
  onConfirm,
}: {
  total: number;
  disabled: boolean;
  onConfirm: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="secondary" disabled={disabled}>
          <RefreshCw className="size-4" />
          Re-scan all
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Re-scan your whole library?</DialogTitle>
          <DialogDescription>
            This re-checks every categorised and uncategorised item (up to ~{total}{" "}
            LLM call{total === 1 ? "" : "s"}, which costs money) against your
            current topics, and may move items between topics — use it after adding
            new topics you want applied everywhere. Items you've assigned by hand
            are left alone. To speed it up, raise <code>CLASSIFY_CONCURRENCY</code>.
          </DialogDescription>
        </DialogHeader>
        <div className="mt-4 flex justify-end gap-2">
          <DialogClose asChild>
            <Button size="sm" variant="ghost">
              Cancel
            </Button>
          </DialogClose>
          <Button
            size="sm"
            onClick={() => {
              setOpen(false);
              onConfirm();
            }}
          >
            <RefreshCw className="size-4" />
            Re-scan everything
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
// Per-topic re-scan: re-check a topic's members against the current taxonomy
// (behind a cost confirm, since it costs one LLM call per member and moves items)
// --------------------------------------------------------------------------- //

function RescanButton({
  topic,
  disabled,
  onConfirm,
}: {
  topic: TopicItem;
  disabled: boolean;
  onConfirm: () => void;
}) {
  const [open, setOpen] = useState(false);
  const n = topic.count;
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Tooltip>
        <TooltipTrigger asChild>
          <DialogTrigger asChild>
            <Button
              size="icon-sm"
              variant="ghost"
              disabled={disabled}
              aria-label="Re-scan members"
            >
              <RefreshCw className="size-3.5" />
            </Button>
          </DialogTrigger>
        </TooltipTrigger>
        <TooltipContent>Re-scan items for a better-fitting topic</TooltipContent>
      </Tooltip>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Re-scan “{topic.label}”?</DialogTitle>
          <DialogDescription>
            This re-checks its {n} item{n === 1 ? "" : "s"} against your current
            topics — one LLM call each (~{n} call{n === 1 ? "" : "s"}), which costs
            money — and may move items to a better-fitting topic. Items you've
            assigned by hand are left alone.
          </DialogDescription>
        </DialogHeader>
        <div className="mt-4 flex justify-end gap-2">
          <DialogClose asChild>
            <Button size="sm" variant="ghost">
              Cancel
            </Button>
          </DialogClose>
          <Button
            size="sm"
            onClick={() => {
              setOpen(false);
              onConfirm();
            }}
          >
            <RefreshCw className="size-4" />
            Re-scan {n}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
// Proposal review card
// --------------------------------------------------------------------------- //

function ProposalCard({
  proposal,
  topics,
}: {
  proposal: TopicProposal;
  topics: TopicItem[];
}) {
  const accept = useAcceptProposal();
  const reject = useRejectProposal();
  const [label, setLabel] = useState(proposal.proposed_label);
  const busy = accept.isPending || reject.isPending;

  return (
    <div className="rounded-lg border border-border bg-surface/40 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className="h-8 max-w-[220px]"
          aria-label="Proposed topic label"
        />
        <span className="font-mono text-[11px] tabular-nums text-fg-subtle">
          {proposal.item_count} item{proposal.item_count === 1 ? "" : "s"}
        </span>
        <div className="ml-auto flex items-center gap-1.5">
          <Button
            size="sm"
            disabled={busy || !label.trim()}
            onClick={() => accept.mutate({ id: proposal.id, body: { label: label.trim() } })}
          >
            <Check className="size-3.5" /> Accept
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="sm" variant="secondary" disabled={busy || topics.length === 0}>
                <GitMerge className="size-3.5" /> Merge into
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {topics.map((t) => (
                <DropdownMenuItem
                  key={t.id}
                  onSelect={() => accept.mutate({ id: proposal.id, body: { topic_id: t.id } })}
                >
                  {t.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() => reject.mutate(proposal.id)}
          >
            <X className="size-3.5" /> Reject
          </Button>
        </div>
      </div>
      {proposal.rationale && (
        <p className="mt-2 text-[13px] text-fg-muted">{proposal.rationale}</p>
      )}
      {proposal.items.length > 0 && (
        <ul className="mt-2 space-y-0.5">
          {proposal.items.slice(0, 6).map((it) => (
            <li key={it.id} className="truncate text-[12px] text-fg-subtle">
              · {it.title ?? "Untitled"}
            </li>
          ))}
          {proposal.items.length > 6 && (
            <li className="text-[12px] text-fg-subtle">
              …and {proposal.items.length - 6} more
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Manage: create + per-topic row
// --------------------------------------------------------------------------- //

function CreateTopicRow() {
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

function TopicRow({
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
                  className={cn("text-fg-subtle hover:text-red-500")}
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
