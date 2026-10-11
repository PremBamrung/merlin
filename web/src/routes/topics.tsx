import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Check,
  ChevronRight,
  GitMerge,
  MessageSquare,
  MoreHorizontal,
  Plus,
  Settings2,
  Sparkles,
  Tags as TagsIcon,
  X,
} from "lucide-react";
import {
  useAcceptProposal,
  useProposals,
  useRejectProposal,
  useTopicDetail,
  useTopicOverview,
  useTopics,
  useUncategorisedCount,
  type TopicItem,
} from "@/hooks/useTopics";
import { useTopicTasks, type TopicTasks } from "@/hooks/useTopicTasks";
import { useItems } from "@/hooks/useItems";
import { useItemHref } from "@/hooks/useItemHref";
import type { TopicCard as TopicCardData, TopicProposal } from "@/lib/api/endpoints";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { Skeleton } from "@/components/ui/skeleton";
import { CardGridSkeleton } from "@/components/common/Skeletons";
import { ItemGrid } from "@/components/items/ItemGrid";
import { PanelSlot } from "@/components/layout/panel";
import { PanelLink, PanelSearch, PanelSection } from "@/components/layout/PanelParts";
import { BackfillButton, ReclassifyAllButton, RescanButton } from "@/components/topics/ConfirmButtons";
import { CreateTopicRow, TopicRow } from "@/components/topics/ManageList";
import { UNCATEGORISED, libraryHref } from "@/lib/libraryView";
import { formatDuration, thousands, thumbnailUrl } from "@/lib/format";
import { cn, randomId } from "@/lib/utils";

/**
 * The Topics place (docs/EVERYDAY_AI_PLAN.md § Topics / Insights; mockup
 * `#topics`, `#topic`, `#topic-proposals`):
 *   /topics            overview — topic cards with share bars, previews, Ask
 *   /topics/:slug      one topic — stats, sub-tags, channels, its items
 *   /topics/proposals  the review queue — accept / merge into / dismiss
 *   /topics/manage     rename, re-scan, merge, archive, delete, create
 * Every page shares the panel (what's waiting + the taxonomy) and the
 * background-task strip.
 */

/** "Catch me up on Dofus" — asked as a new chat thread. */
function useAsk() {
  const navigate = useNavigate();
  return (q: string) => navigate(`/chat?thread=${randomId()}&q=${encodeURIComponent(q)}`);
}

const pct = (share: number) =>
  share >= 0.1 ? `${Math.round(share * 100)}%` : `${(share * 100).toFixed(1)}%`;

// --------------------------------------------------------------------------- //
// Shared: panel, task strip, share bar, back link
// --------------------------------------------------------------------------- //

function TopicsPanel({ current }: { current?: string }) {
  const overview = useTopicOverview().data;
  const proposals = useProposals().data?.length ?? 0;
  const uncat = useUncategorisedCount().data ?? 0;
  const topics = overview?.topics ?? [];
  const max = Math.max(1, ...topics.map((t) => t.count));
  return (
    <PanelSlot title="Topics" sub={overview ? `${topics.length} active` : undefined}>
      <PanelSearch placeholder="Search topics" />
      {(proposals > 0 || uncat > 0) && (
        <PanelSection title="Waiting on you">
          {proposals > 0 && (
            <PanelLink
              to="/topics/proposals"
              on={current === "proposals"}
              icon={Sparkles}
              label="Proposals"
              trail={
                <span className="ml-auto flex items-center gap-1.5 font-mono text-[11px] font-medium text-signal">
                  <span className="size-1.5 rounded-full bg-signal" />
                  {proposals}
                </span>
              }
            />
          )}
          {uncat > 0 && (
            <PanelLink
              to={libraryHref({ kind: "topic", slug: UNCATEGORISED })}
              icon={TagsIcon}
              label="Uncategorised"
              count={uncat}
            />
          )}
        </PanelSection>
      )}
      <PanelSection
        title={`Active · ${topics.length}`}
        right={
          <Link to="/topics/manage" className="hover:underline hover:underline-offset-[3px]">
            manage
          </Link>
        }
      >
        {topics.map((t) => (
          <PanelLink
            key={t.slug}
            to={`/topics/${t.slug}`}
            on={current === t.slug}
            lead={
              <span className="h-1 w-[22px] shrink-0 overflow-hidden rounded-full bg-ui-chart-track">
                <span
                  className="block h-full rounded-full bg-ui-chart-1"
                  style={{ width: `${Math.max(8, (t.count / max) * 100)}%` }}
                />
              </span>
            }
            label={t.label}
            trail={
              <span className="ml-auto flex shrink-0 items-center gap-1.5 font-mono text-[11px] tabular-nums text-fg-subtle">
                {t.new_count > 0 && (
                  <span className="size-1.5 rounded-full bg-signal" title={`${t.new_count} new`} />
                )}
                {thousands(t.count)}
              </span>
            }
          />
        ))}
      </PanelSection>
      <div className="pt-1">
        <PanelLink to="/topics/manage" icon={Plus} label="New topic" />
      </div>
    </PanelSlot>
  );
}

function TaskStrip({ tasks }: { tasks: TopicTasks }) {
  if (!tasks.running) return null;
  return (
    <div className="flex items-center gap-3 rounded-[14px] border border-border bg-surface/50 px-4 py-3 text-[13px] text-fg-muted">
      <span className="size-1.5 shrink-0 animate-pulse rounded-full bg-signal" />
      <span className="flex-1">
        {tasks.message}
        {typeof tasks.progress === "number" && ` (${tasks.progress}%)`}
      </span>
      <Button size="sm" variant="ghost" disabled={tasks.stopping} onClick={tasks.cancel}>
        <X className="size-3.5" />
        {tasks.stopping ? "Stopping…" : "Cancel"}
      </Button>
    </div>
  );
}

function ShareBar({ share }: { share: number }) {
  return (
    <div className="h-1.5 overflow-hidden rounded-full bg-ui-chart-track">
      <div
        className="h-full rounded-full bg-ui-chart-1"
        style={{ width: `${Math.max(1.5, share * 100)}%` }}
      />
    </div>
  );
}

function BackLink() {
  return (
    <Link
      to="/topics"
      className="inline-flex items-center gap-1.5 text-[14px] text-fg-muted transition-colors hover:text-fg"
    >
      <ArrowLeft className="size-4" /> Topics
    </Link>
  );
}

// --------------------------------------------------------------------------- //
// /topics — the overview
// --------------------------------------------------------------------------- //

export default function TopicsRoute() {
  const overview = useTopicOverview();
  const proposals = useProposals().data ?? [];
  const uncat = useUncategorisedCount().data ?? 0;
  const tasks = useTopicTasks();
  const navigate = useNavigate();
  const topics = overview.data?.topics ?? [];
  const moving = topics.filter((t) => t.new_count > 0).length;
  // Upper bound for the full re-scan confirm (topic counts over-count
  // multi-topic items); the task reports the exact count once it starts.
  const estimate = topics.reduce((s, t) => s + t.count, 0) + uncat;

  return (
    <div className="space-y-5">
      <TopicsPanel />
      <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
        <h1 className="font-display text-[26px] font-semibold leading-9 tracking-[-0.03em] md:text-[30px]">
          Topics
        </h1>
        <span className="pb-[7px] font-mono text-[12px] text-fg-subtle">
          {topics.length} active · {thousands(overview.data?.total ?? 0)} items
        </span>
        <div className="ml-auto flex items-center gap-2">
          <ReclassifyAllButton
            total={estimate}
            disabled={tasks.busy || !topics.length}
            onConfirm={tasks.startRescanAll}
          />
          <Button size="sm" onClick={() => navigate("/topics/manage")}>
            <Plus className="size-4" /> New topic
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label="More topic actions">
                <MoreHorizontal className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={tasks.startDiscovery} disabled={tasks.busy}>
                <Sparkles className="size-3.5" /> Find new topics
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/topics/manage">
                  <Settings2 className="size-3.5" /> Manage topics
                </Link>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <TaskStrip tasks={tasks} />

      {(proposals.length > 0 || uncat > 0) && (
        <div className="grid gap-3.5 md:grid-cols-[minmax(0,1.75fr)_minmax(0,1fr)]">
          {proposals.length > 0 && (
            <Link
              to="/topics/proposals"
              className="flex items-center gap-3.5 rounded-[14px] border border-signal/45 bg-signal/[0.06] px-4 py-3.5 transition-colors hover:bg-signal/10"
            >
              <span className="grid size-10 shrink-0 place-items-center rounded-[10px] bg-signal/15 text-signal">
                <Sparkles className="size-[18px]" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-[15px] font-medium text-fg">
                  {proposals.length} proposal{proposals.length === 1 ? "" : "s"} waiting
                </span>
                <span className="block truncate text-[14px] text-fg-muted">
                  {proposals
                    .slice(0, 3)
                    .map((p) => `${p.proposed_label} · ${p.item_count}`)
                    .join(" · ")}
                </span>
              </span>
              <span className="flex shrink-0 items-center gap-1 text-[14px] text-fg">
                Review <ChevronRight className="size-4" />
              </span>
            </Link>
          )}
          {uncat > 0 && (
            <div
              className={cn(
                "flex items-center gap-3 rounded-[14px] border border-border bg-surface/50 px-4 py-3.5",
                proposals.length === 0 && "md:col-span-2",
              )}
            >
              <span className="font-display text-[17px] font-semibold tabular-nums text-fg">{uncat}</span>
              <Link
                to={libraryHref({ kind: "topic", slug: UNCATEGORISED })}
                className="flex-1 text-[14px] text-fg-muted hover:text-fg"
              >
                items without a topic
              </Link>
              <BackfillButton
                uncat={uncat}
                label="Classify"
                disabled={tasks.busy || !topics.length}
                onConfirm={tasks.startBackfill}
              />
            </div>
          )}
        </div>
      )}

      <div className="flex items-baseline gap-2.5 pt-2">
        <h2 className="font-display text-[18px] font-semibold">Active</h2>
        <span className="font-mono text-[12px] text-fg-subtle">
          by size{moving > 0 && ` · ${moving} moving this week`}
        </span>
      </div>

      {overview.isLoading ? (
        <CardGridSkeleton count={6} />
      ) : overview.isError ? (
        <ErrorState error={overview.error} onRetry={() => overview.refetch()} />
      ) : topics.length === 0 ? (
        <EmptyState
          icon={TagsIcon}
          title="No topics yet"
          description={
            uncat > 0
              ? `You have ${uncat} uncategorised items. Let Merlin propose topics, or add your own.`
              : "Add a topic to start organising your library."
          }
          action={
            <Button size="sm" onClick={tasks.startDiscovery} disabled={tasks.busy}>
              <Sparkles className="size-4" /> Find topics
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-[repeat(auto-fill,minmax(300px,1fr))]">
          {topics.map((t) => (
            <TopicCard key={t.slug} topic={t} />
          ))}
        </div>
      )}
    </div>
  );
}

function TopicCard({ topic }: { topic: TopicCardData }) {
  const ask = useAsk();
  const extra = topic.count - topic.preview.length;
  return (
    <div className="relative flex flex-col rounded-[14px] border border-border bg-[color-mix(in_srgb,var(--color-surface)_50%,transparent)] p-4 transition-colors hover:border-ui-hover-border hover:bg-surface">
      <div className="flex items-baseline gap-2">
        {/* The whole card opens the topic (the link's ::after covers it); Ask
            sits above that layer. */}
        <Link
          to={`/topics/${topic.slug}`}
          className="min-w-0 truncate font-display text-[17px] font-semibold tracking-[-0.01em] text-fg after:absolute after:inset-0 after:rounded-[14px]"
        >
          {topic.label}
        </Link>
        <span className="font-mono text-[12px] tabular-nums text-fg-subtle">{thousands(topic.count)}</span>
        {topic.new_count > 0 && (
          <span className="ml-auto flex shrink-0 items-center gap-1.5 font-mono text-[11.5px] font-medium text-signal">
            <span className="size-1.5 rounded-full bg-signal" />↑ {topic.new_count} new
          </span>
        )}
      </div>
      <div className="mt-3">
        <ShareBar share={topic.share} />
      </div>
      <p className="mt-2 font-mono text-[11px] text-fg-subtle">{pct(topic.share)} of your library</p>
      <div className="mt-3 grid grid-cols-3 gap-1.5">
        {topic.preview.map((it) => {
          const thumb = thumbnailUrl(it);
          return (
            <span key={it.id} className="aspect-video overflow-hidden rounded-md bg-surface-2">
              {thumb && <img src={thumb} alt="" loading="lazy" className="size-full object-cover" />}
            </span>
          );
        })}
        {topic.preview.length > 0 && topic.preview.length < 3 && extra > 0 && (
          <span className="grid aspect-video place-items-center rounded-md bg-surface-2 font-mono text-[12px] text-fg-subtle">
            +{extra}
          </span>
        )}
        {topic.preview.length === 0 && (
          <span className="col-span-3 grid h-[54px] place-items-center rounded-md border border-dashed border-border font-mono text-[11px] text-fg-subtle">
            nothing in it yet
          </span>
        )}
      </div>
      <div className="mt-3.5 flex items-center gap-2">
        <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-fg-subtle">
          {topic.top_tags.map((t) => `#${t}`).join(" ")}
        </span>
        <Button
          variant="outline"
          size="sm"
          className="relative z-[1] h-7 rounded-full px-3"
          onClick={() => ask(`Catch me up on ${topic.label}`)}
        >
          <MessageSquare className="size-3.5" /> Ask
        </Button>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// /topics/:slug — one topic
// --------------------------------------------------------------------------- //

const ITEMS = 24;

export function TopicDetailRoute() {
  const { slug = "" } = useParams();
  const detail = useTopicDetail(slug);
  const tasks = useTopicTasks();
  const ask = useAsk();
  const [tag, setTag] = useState<string | null>(null);
  const [channel, setChannel] = useState<string | null>(null);
  const items = useItems({
    topics: [slug],
    tags: tag ? [tag] : undefined,
    channel: channel ?? undefined,
    sort: "newest",
    per_page: ITEMS,
  });
  const t = detail.data;

  if (detail.isLoading)
    return (
      <div className="space-y-5">
        <TopicsPanel current={slug} />
        <Skeleton className="h-10 w-64" />
        <CardGridSkeleton count={6} />
      </div>
    );
  if (detail.isError || !t)
    return (
      <div className="space-y-5">
        <TopicsPanel current={slug} />
        <BackLink />
        <ErrorState error={detail.error ?? "Topic not found."} onRetry={() => detail.refetch()} />
      </div>
    );

  const hours = t.seconds / 3600;
  const stats: [string, string][] = [
    [thousands(t.count), t.count === 1 ? "item" : "items"],
    [pct(t.share), "of library"],
  ];
  if (t.seconds > 0)
    stats.push([hours >= 1 ? `${Math.round(hours)}h` : `${Math.round(t.seconds / 60)}m`, "of video"]);
  stats.push([thousands(t.channel_count), t.channel_count === 1 ? "channel" : "channels"]);
  const shown = items.data?.items.length ?? 0;
  const matching = items.data?.total ?? 0;
  const asTopicItem: TopicItem = t;

  return (
    <div className="space-y-5">
      <TopicsPanel current={slug} />
      <BackLink />
      <div>
        <p className="eyebrow">
          Topic ·{" "}
          {t.origin === "user" ? "added by you" : t.origin === "seed" ? "starter topic" : "proposed by Merlin"}
        </p>
        <h1 className="mt-2 font-display text-[30px] font-semibold leading-tight tracking-[-0.03em] md:text-[38px]">
          {t.label}
        </h1>
        {t.description && <p className="mt-1 max-w-[70ch] text-[14px] text-fg-muted">{t.description}</p>}
      </div>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <p className="flex flex-wrap items-baseline gap-x-5 gap-y-1 text-[14px] text-fg-muted">
          {stats.map(([n, l]) => (
            <span key={l}>
              <b className="font-mono font-medium text-fg">{n}</b> {l}
            </span>
          ))}
          {t.new_count > 0 && (
            <span className="flex items-center gap-1.5 text-signal">
              <span className="size-1.5 rounded-full bg-signal" />
              <b className="font-mono font-medium">{t.new_count}</b> new this week
            </span>
          )}
        </p>
        <div className="ml-auto flex items-center gap-2">
          <Button size="sm" onClick={() => ask(`Catch me up on ${t.label}`)}>
            <Sparkles className="size-3.5" /> Catch me up
          </Button>
          <Button variant="outline" size="sm" onClick={() => ask(`What does my library say about ${t.label}?`)}>
            <MessageSquare className="size-3.5" /> Ask about {t.label}
          </Button>
          <RescanButton
            topic={asTopicItem}
            disabled={tasks.busy || t.count === 0}
            onConfirm={() => tasks.startRescan(asTopicItem)}
          />
          <Button variant="ghost" size="icon-sm" asChild>
            <Link to="/topics/manage" aria-label="Manage topics" title="Rename, merge, archive or delete">
              <MoreHorizontal className="size-4" />
            </Link>
          </Button>
        </div>
      </div>

      <TaskStrip tasks={tasks} />

      {t.tags.length > 0 && (
        <ChipRow label="Sub-tags">
          <FacetChip on={tag === null} onClick={() => setTag(null)} count={t.count}>
            All
          </FacetChip>
          {t.tags.map((x) => (
            <FacetChip
              key={x.name}
              on={tag === x.name}
              onClick={() => setTag(tag === x.name ? null : x.name)}
              count={x.count}
            >
              #{x.name}
            </FacetChip>
          ))}
        </ChipRow>
      )}
      {t.channels.length > 0 && (
        <ChipRow label="Channels">
          {t.channels.map((x) => (
            <FacetChip
              key={x.name}
              on={channel === x.name}
              onClick={() => setChannel(channel === x.name ? null : x.name)}
            >
              {x.name}
            </FacetChip>
          ))}
          {t.channel_count > t.channels.length && (
            <span className="inline-flex h-[30px] shrink-0 items-center rounded-full border border-border px-3 font-mono text-[12px] text-fg-subtle">
              +{t.channel_count - t.channels.length}
            </span>
          )}
        </ChipRow>
      )}

      <div className="flex items-baseline gap-2.5 pt-1">
        <h2 className="font-display text-[18px] font-semibold">Items</h2>
        <span className="hidden font-mono text-[12px] text-fg-subtle sm:inline">
          newest first · {shown} of {thousands(matching)} shown
        </span>
        {matching > shown && (
          <Link
            to={`/library?topics=${encodeURIComponent(slug)}`}
            className="ml-auto inline-flex items-center gap-1 text-[13px] text-ui-link hover:underline hover:underline-offset-[3px]"
          >
            See all in the Library <ChevronRight className="size-3.5" />
          </Link>
        )}
      </div>
      {items.isLoading ? <CardGridSkeleton count={6} /> : <ItemGrid items={items.data?.items ?? []} />}
    </div>
  );
}

function ChipRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <span className="hidden w-[76px] shrink-0 font-mono text-[11px] uppercase tracking-[0.08em] text-fg-subtle sm:block">
        {label}
      </span>
      <div className="no-scrollbar flex min-w-0 gap-1.5 overflow-x-auto">{children}</div>
    </div>
  );
}

function FacetChip({
  on,
  onClick,
  count,
  children,
}: {
  on: boolean;
  onClick: () => void;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={on}
      className={cn(
        "inline-flex h-[30px] shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 text-[13px] transition-colors",
        on
          ? "border-ui-toggle-on-border bg-ui-toggle-on-bg text-ui-toggle-on-fg"
          : "border-border text-fg-muted hover:border-border-strong hover:text-fg",
      )}
    >
      {children}
      {count != null && <span className="font-mono text-[11px] text-fg-subtle">{count}</span>}
    </button>
  );
}

// --------------------------------------------------------------------------- //
// /topics/proposals — the review queue
// --------------------------------------------------------------------------- //

export function TopicProposalsRoute() {
  const proposals = useProposals();
  const topics = useTopics("active").data ?? [];
  const tasks = useTopicTasks();
  const pending = proposals.data ?? [];

  return (
    <div className="mx-auto max-w-[1400px] space-y-5">
      <TopicsPanel current="proposals" />
      <BackLink />
      <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
        <h1 className="font-display text-[30px] font-semibold leading-9 tracking-[-0.03em]">Proposals</h1>
        {pending.length > 0 && (
          <span className="flex items-center gap-1.5 pb-1.5 font-mono text-[12px] text-fg-subtle">
            <span className="size-1.5 rounded-full bg-signal" />
            {pending.length} waiting
          </span>
        )}
        <Button variant="ghost" size="sm" className="ml-auto" onClick={tasks.startDiscovery} disabled={tasks.busy}>
          <Sparkles className="size-3.5" /> Look for more
        </Button>
      </div>
      <p className="max-w-[72ch] text-[15px] leading-6 text-fg-muted">
        Merlin noticed clusters your topics don't cover. Nothing changes until you accept —
        accepting moves the items and keeps your tags.
      </p>

      <TaskStrip tasks={tasks} />

      {proposals.isLoading ? (
        <Skeleton className="h-56 w-full rounded-[14px]" />
      ) : pending.length === 0 ? (
        <EmptyState
          icon={Check}
          title="Nothing waiting"
          description="When Merlin finds a cluster your topics don't cover, it shows up here for you to accept, merge or dismiss."
          action={
            <Button size="sm" variant="secondary" onClick={tasks.startDiscovery} disabled={tasks.busy}>
              <Sparkles className="size-3.5" /> Look for topics
            </Button>
          }
        />
      ) : (
        <div className="space-y-4">
          {pending.map((p) => (
            <ProposalCard key={p.id} proposal={p} topics={topics} />
          ))}
        </div>
      )}
    </div>
  );
}

function ProposalCard({ proposal, topics }: { proposal: TopicProposal; topics: TopicItem[] }) {
  const accept = useAcceptProposal();
  const reject = useRejectProposal();
  const itemHref = useItemHref();
  const [label, setLabel] = useState(proposal.proposed_label);
  const busy = accept.isPending || reject.isPending;
  const examples = (proposal.items ?? []).slice(0, 4);
  const more = (proposal.items?.length ?? 0) - examples.length;

  return (
    // Gold edge: a proposal is something waiting on you.
    <div className="grid gap-6 rounded-[14px] border border-border bg-surface/50 p-[22px] shadow-[inset_3px_0_0_var(--color-signal)] lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      <div className="min-w-0">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-signal">
          Proposed topic · {proposal.item_count} item{proposal.item_count === 1 ? "" : "s"}
        </p>
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          aria-label="Topic name"
          className="-ml-1 mt-2 w-full rounded-md border border-transparent bg-transparent px-1 py-0.5 font-display text-[24px] font-semibold tracking-[-0.02em] text-fg outline-none transition-colors hover:border-border focus:border-ui-focus-border"
        />
        {proposal.rationale && (
          <p className="mt-2 max-w-[62ch] text-[15px] leading-[22px] text-fg-muted">{proposal.rationale}</p>
        )}
        <div className="mt-5 flex flex-wrap gap-2">
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
                <GitMerge className="size-3.5" /> Merge into…
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="max-h-80 overflow-y-auto">
              {topics.map((t) => (
                <DropdownMenuItem
                  key={t.id}
                  onSelect={() => accept.mutate({ id: proposal.id, body: { topic_id: t.id } })}
                >
                  {t.label}
                  <span className="ml-auto pl-4 font-mono text-[11px] text-fg-subtle">{t.count}</span>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => reject.mutate(proposal.id)}>
            Dismiss
          </Button>
        </div>
      </div>
      {examples.length > 0 && (
        <div className="min-w-0">
          <p className="eyebrow mb-3">Examples</p>
          <div className="space-y-2">
            {examples.map((it) => {
              const thumb =
                it.thumbnail_url ??
                (it.source_id ? thumbnailUrl({ source_type: "youtube", source_id: it.source_id }) : null);
              const { to, state } = itemHref(it.id);
              const duration = formatDuration(it.duration);
              return (
                <Link
                  key={it.id}
                  to={to}
                  state={state}
                  className="grid grid-cols-[112px_minmax(0,1fr)] items-center gap-3 rounded-[10px] p-1 transition-colors hover:bg-surface-2"
                >
                  <span className="relative aspect-video overflow-hidden rounded-md bg-surface-2">
                    {thumb && <img src={thumb} alt="" loading="lazy" className="size-full object-cover" />}
                    {duration && (
                      <span className="absolute bottom-1 right-1 rounded bg-black/75 px-1 py-0.5 font-mono text-[10px] leading-none text-white">
                        {duration}
                      </span>
                    )}
                  </span>
                  <span className="min-w-0">
                    <span className="line-clamp-2 text-[14px] leading-5 text-fg">{it.title ?? "Untitled"}</span>
                    {it.channel && (
                      <span className="block truncate font-mono text-[11px] text-fg-subtle">{it.channel}</span>
                    )}
                  </span>
                </Link>
              );
            })}
          </div>
          {more > 0 && <p className="mt-2 font-mono text-[11px] text-fg-subtle">+ {more} more</p>}
        </div>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// /topics/manage — the full management list
// --------------------------------------------------------------------------- //

export function TopicManageRoute() {
  const topics = useTopics("active");
  const uncat = useUncategorisedCount().data ?? 0;
  const tasks = useTopicTasks();
  const list = useMemo(() => topics.data ?? [], [topics.data]);
  const estimate = list.reduce((s, t) => s + t.count, 0) + uncat;

  return (
    <div className="mx-auto max-w-[900px] space-y-6">
      <TopicsPanel />
      <BackLink />
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-[26px] font-semibold tracking-[-0.03em]">Manage topics</h1>
          <p className="mt-1 text-[13px] text-fg-muted">
            Rename, re-scan, merge, archive or delete — and add your own.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ReclassifyAllButton
            total={estimate}
            disabled={tasks.busy || !list.length}
            onConfirm={tasks.startRescanAll}
          />
          <BackfillButton uncat={uncat} disabled={tasks.busy || !list.length} onConfirm={tasks.startBackfill} />
          <Button size="sm" onClick={tasks.startDiscovery} disabled={tasks.busy}>
            <Sparkles className="size-4" />
            {tasks.running && tasks.kind === "discovery" ? "Finding topics…" : "Find topics"}
          </Button>
        </div>
      </div>

      <TaskStrip tasks={tasks} />

      <CreateTopicRow />
      {topics.isLoading ? null : list.length === 0 ? (
        <EmptyState icon={TagsIcon} title="No topics yet" description="Add a topic above, or let Merlin find some." />
      ) : (
        <ul className="divide-y divide-border rounded-[14px] border border-border">
          {list.map((t) => (
            <TopicRow key={t.id} topic={t} all={list} busy={tasks.busy} onRescan={tasks.startRescan} />
          ))}
        </ul>
      )}
    </div>
  );
}
