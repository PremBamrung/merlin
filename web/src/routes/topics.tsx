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
  Tags as TagsIcon,
} from "lucide-react";
import {
  useAcceptProposal,
  useCreateTopic,
  useDeleteTopic,
  usePatchTopic,
  useProposals,
  useProposeTopics,
  useRejectProposal,
  useTopics,
  useUncategorisedCount,
  type TopicItem,
} from "@/hooks/useTopics";
import { getTask, type TopicProposal } from "@/lib/api/endpoints";
import { keys } from "@/lib/queryKeys";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EmptyState } from "@/components/common/EmptyState";
import { toast } from "@/components/ui/toaster";
import { cn } from "@/lib/utils";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

export default function TopicsRoute() {
  const topics = useTopics("active");
  const proposals = useProposals();
  const uncategorised = useUncategorisedCount();
  const propose = useProposeTopics();
  const qc = useQueryClient();

  // Poll the background proposal task until it settles, then refresh the lists.
  // taskId is left set once terminal (polling just stops); `running` is derived
  // from the live status, so the effect never needs to write state.
  const [taskId, setTaskId] = useState<string | null>(null);
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
    if (status === "failed") toast.error("Topic discovery failed");
    else toast.success("Topic discovery complete");
  }, [task.data?.status, qc]);

  const running = !!taskId && !TERMINAL.has(task.data?.status ?? "");
  const startDiscovery = () =>
    propose.mutate(undefined, { onSuccess: (r) => setTaskId(r.task_id) });

  const pending = proposals.data ?? [];
  const uncat = uncategorised.data ?? 0;

  return (
    <div className="mx-auto max-w-[900px] space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-semibold">Topics</h1>
          <p className="mt-1 text-[13px] text-fg-muted">
            Your navigation taxonomy — the buckets the Feed filters by.
          </p>
        </div>
        <Button size="sm" onClick={startDiscovery} disabled={running || propose.isPending}>
          <Sparkles className="size-4" />
          {running ? "Finding topics…" : "Find topics"}
          {uncat > 0 && !running && (
            <span className="ml-1 font-mono text-[11px] tabular-nums opacity-80">
              {uncat}
            </span>
          )}
        </Button>
      </div>

      {running && (
        <div className="rounded-lg border border-border bg-surface/40 p-4 text-[13px] text-fg-muted">
          {task.data?.message || "Clustering uncategorised items…"}
          {typeof task.data?.progress === "number" && ` (${task.data.progress}%)`}
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
              <TopicRow key={t.id} topic={t} all={topics.data!} />
            ))}
          </ul>
        )}
      </section>
    </div>
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

function TopicRow({ topic, all }: { topic: TopicItem; all: TopicItem[] }) {
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
            <Button size="icon-sm" variant="ghost" onClick={() => setEditing(true)} aria-label="Rename">
              <Pencil className="size-3.5" />
            </Button>
            {others.length > 0 && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button size="icon-sm" variant="ghost" aria-label="Merge into">
                    <GitMerge className="size-3.5" />
                  </Button>
                </DropdownMenuTrigger>
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
            <Button
              size="icon-sm"
              variant="ghost"
              onClick={() => patch.mutate({ id: topic.id, body: { archive: true } })}
              aria-label="Archive"
            >
              <Archive className="size-3.5" />
            </Button>
            <Button
              size="icon-sm"
              variant="ghost"
              onClick={() => del.mutate(topic.id)}
              aria-label="Delete"
              className={cn("text-fg-subtle hover:text-red-500")}
            >
              <X className="size-3.5" />
            </Button>
          </div>
        </>
      )}
    </li>
  );
}
