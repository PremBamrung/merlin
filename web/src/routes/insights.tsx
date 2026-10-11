import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BarChart3, ChevronRight, Coins, LayoutGrid, List, PlayCircle } from "lucide-react";
import { useChannelCount, useTimeline, useTopChannels, useUsage } from "@/hooks/useInsights";
import { useTopicOverview, useTopics } from "@/hooks/useTopics";
import { useUnreadCount } from "@/hooks/useFeed";
import { useChatThreads } from "@/hooks/useChatThreads";
import type { TimelinePoint, Usage } from "@/lib/api/endpoints";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { PanelSlot } from "@/components/layout/panel";
import { PanelButton, PanelSection } from "@/components/layout/PanelParts";
import { CHART } from "@/lib/chartColors";
import { thousands } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useCountUp } from "@/lib/motion";

/**
 * Insights (docs/EVERYDAY_AI_PLAN.md § Topics / Insights; mockup `#insights`):
 * headline tiles, items added with the one-off import split out, where the
 * library goes, top channels and LLM spend. One series per chart, in sky; every
 * chart has hover values and a "View as table". The range (7d / 30d / All) is
 * applied client-side and kept in the URL.
 */

type Range = "7d" | "30d" | "all";
const RANGES: { id: Range; label: string; long: string; days: number | null }[] = [
  { id: "7d", label: "7d", long: "Last 7 days", days: 7 },
  { id: "30d", label: "30d", long: "Last 30 days", days: 30 },
  { id: "all", label: "All", long: "All time", days: null },
];

const DAY = 86_400_000;
const ymd = (d: Date) => d.toISOString().slice(0, 10);
const shortDate = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });

function usd(n: number): string {
  if (!n) return "$0.00";
  if (n < 0.01) return "$" + n.toFixed(4);
  return "$" + n.toFixed(2);
}

const pct = (n: number, total: number) => {
  const s = total ? n / total : 0;
  return s >= 0.1 ? `${Math.round(s * 100)}%` : `${(s * 100).toFixed(1)}%`;
};

/**
 * A one-off bulk import (hundreds of items in a day) flattens every other bar
 * to nothing. A day well above the rest — ≥ 50 items and ≥ 10× the median busy
 * day — is reported separately and left out of the bars.
 */
function findSpike(points: TimelinePoint[]): TimelinePoint | null {
  const busy = points
    .filter((p) => p.count > 0)
    .map((p) => p.count)
    .sort((a, b) => a - b);
  if (busy.length < 3) return null;
  const median = busy[Math.floor(busy.length / 2)];
  const top = points.reduce((a, b) => (b.count > a.count ? b : a), points[0]);
  return top.count >= 50 && top.count >= 10 * median ? top : null;
}

type Bucket = { key: string; label: string; count: number; spike?: number };

/** Per day for the short ranges (missing days filled), per week (Monday) for all. */
function bucket(
  points: TimelinePoint[],
  range: Range,
  spike: TimelinePoint | null,
  now: number,
): Bucket[] {
  const byDay = new Map(points.map((p) => [p.date, p.count]));
  const days = RANGES.find((x) => x.id === range)!.days;
  if (days) {
    const out: Bucket[] = [];
    for (let i = days - 1; i >= 0; i--) {
      const d = ymd(new Date(now - i * DAY));
      const n = byDay.get(d) ?? 0;
      const isSpike = spike?.date === d;
      out.push({ key: d, label: shortDate(d), count: isSpike ? 0 : n, spike: isSpike ? n : undefined });
    }
    return out;
  }
  if (!points.length) return [];
  const monday = (iso: string) => {
    const d = new Date(`${iso}T00:00:00Z`);
    d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
    return ymd(d);
  };
  const weeks = new Map<string, Bucket>();
  const first = new Date(`${monday(points[0].date)}T00:00:00Z`).getTime();
  for (let t = first; t <= now; t += 7 * DAY) {
    const k = ymd(new Date(t));
    weeks.set(k, { key: k, label: shortDate(k), count: 0 });
  }
  for (const p of points) {
    const w = weeks.get(monday(p.date));
    if (!w) continue;
    if (spike?.date === p.date) w.spike = p.count;
    else w.count += p.count;
  }
  return [...weeks.values()];
}

export default function InsightsRoute() {
  const [params, setParams] = useSearchParams();
  // "Today" for the ranges, fixed for the life of the page (render stays pure).
  const [now] = useState(() => Date.now());
  const range = (RANGES.find((r) => r.id === params.get("range"))?.id ?? "all") as Range;
  const setRange = (r: Range) => setParams(r === "all" ? {} : { range: r }, { replace: true });

  const timeline = useTimeline();
  const channels = useTopChannels(8);
  const channelCount = useChannelCount();
  const usage = useUsage();
  const overview = useTopicOverview();
  const unreadTopics = useTopics("active", true).data;
  const unread = useUnreadCount().data ?? 0;
  const threads = useChatThreads().data;

  const points = useMemo(
    () => [...(timeline.data ?? [])].sort((a, b) => a.date.localeCompare(b.date)),
    [timeline.data],
  );
  const days = RANGES.find((r) => r.id === range)!.days;
  const inRange = useMemo(
    () =>
      days ? points.filter((p) => p.date >= ymd(new Date(now - (days - 1) * DAY))) : points,
    [points, days, now],
  );
  const spike = useMemo(() => findSpike(points), [points]);
  const spikeInRange = spike && inRange.some((p) => p.date === spike.date) ? spike : null;
  const buckets = useMemo(
    () => bucket(inRange, range, spikeInRange, now),
    [inRange, range, spikeInRange, now],
  );
  const added = inRange.reduce((s, p) => s + p.count, 0) - (spikeInRange?.count ?? 0);

  const total = overview.data?.total ?? 0;
  const loading = timeline.isLoading || overview.isLoading;
  const error = timeline.error || overview.error;
  const turns = threads?.length
    ? Math.round(threads.reduce((s, t) => s + t.message_count, 0) / threads.length / 2)
    : 0;
  const rangeLabel = RANGES.find((r) => r.id === range)!.long;
  const since = points[0]?.date;

  return (
    <div className="space-y-4">
      <InsightsPanel range={range} setRange={setRange} />
      <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
        <h1 className="font-display text-[26px] font-semibold leading-9 tracking-[-0.03em] md:text-[30px]">
          Insights
        </h1>
        <span className="pb-[7px] font-mono text-[12px] text-fg-subtle">
          {rangeLabel}
          {range === "all" && since && ` · since ${shortDate(since)}`}
        </span>
        <div
          role="radiogroup"
          aria-label="Range"
          className="ml-auto inline-flex rounded-[9px] border border-border bg-surface p-[3px]"
        >
          {RANGES.map((r) => (
            <button
              key={r.id}
              role="radio"
              aria-checked={range === r.id}
              onClick={() => setRange(r.id)}
              className={cn(
                "rounded-md px-2.5 py-1.5 font-mono text-[12px] transition-colors",
                range === r.id ? "bg-ui-current-bg text-ui-current-fg" : "text-fg-subtle hover:text-fg",
              )}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {error ? (
        <ErrorState error={error} onRetry={() => timeline.refetch()} />
      ) : !loading && total === 0 ? (
        <EmptyState
          icon={BarChart3}
          title="Not enough data yet"
          description="Ingest a few sources and trends will show up here."
        />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <Kpi
              k="Items"
              v={<CountUp n={total} />}
              d={
                range === "all" && spike
                  ? `+${thousands(spike.count)} imported ${shortDate(spike.date)}`
                  : `+${thousands(added)} in range`
              }
            />
            <Kpi
              k="Unread"
              v={
                <span className="flex items-center gap-2">
                  {unread > 0 && <span className="size-2 rounded-full bg-signal" />}
                  {thousands(unread)}
                </span>
              }
              d={
                <Link to="/feed" className="hover:text-fg hover:underline hover:underline-offset-[3px]">
                  open the Feed
                </Link>
              }
            />
            <Kpi k="Channels" v={<CountUp n={channelCount.data?.count ?? 0} />} d="distinct channels" />
            <Kpi
              k="Conversations"
              v={<CountUp n={threads?.length ?? 0} />}
              d={turns ? `avg ${turns} turn${turns === 1 ? "" : "s"}` : "none yet"}
            />
            <Kpi
              k="LLM spend"
              v={usd(usage.data?.total.cost_usd ?? 0)}
              d={`${thousands(usage.data?.total.calls ?? 0)} calls · all time`}
            />
          </div>

          <Card id="activity">
            <CardHead
              title="Items added"
              sub={
                range === "all"
                  ? spike
                    ? `Per week. The one-off import of ${thousands(spike.count)} items on ${shortDate(spike.date)} is split out so the rest stays readable.`
                    : "Per week."
                  : "Per day."
              }
              big={{
                k: range === "all" && spike ? "since import" : rangeLabel.toLowerCase(),
                v: thousands(added),
              }}
            />
            {loading ? (
              <Skeleton className="h-60 w-full" />
            ) : added === 0 && !spikeInRange ? (
              <p className="py-10 text-center text-[14px] text-fg-muted">
                Nothing added in the {rangeLabel.toLowerCase()}.{" "}
                <button onClick={() => setRange("all")} className="text-ui-link hover:underline hover:underline-offset-[3px]">
                  See all time
                </button>
              </p>
            ) : (
              <ItemsChart buckets={buckets} spike={spikeInRange} />
            )}
            <DataTable
              cols={[range === "all" ? "Week of" : "Day", "Items"]}
              rows={buckets
                .filter((b) => b.count || b.spike)
                .map((b) => [b.label, `${b.count}${b.spike ? ` (+${b.spike} import)` : ""}`])}
            />
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card id="topics">
              <CardHead
                title="Where your library goes"
                sub={
                  <>
                    Items per topic.{" "}
                    <span className="inline-block size-1.5 rounded-full bg-signal align-[2px]" /> has unread
                    items.
                  </>
                }
              />
              {overview.isLoading ? (
                <Skeleton className="h-56 w-full" />
              ) : (
                <TopicBars
                  topics={overview.data?.topics ?? []}
                  total={total}
                  unread={new Set((unreadTopics ?? []).map((t) => t.slug))}
                />
              )}
              <Link
                to="/topics"
                className="mt-3 inline-flex items-center gap-1 text-[13px] text-ui-link hover:underline hover:underline-offset-[3px]"
              >
                All topics <ChevronRight className="size-3.5" />
              </Link>
            </Card>
            <Card id="channels">
              <CardHead
                title="Top channels"
                sub={
                  channels.data?.length && total
                    ? `Of ${thousands(channelCount.data?.count ?? 0)} channels; ${channels.data[0].name} alone is ${pct(
                        channels.data[0].count,
                        total,
                      )} of the library.`
                    : "By items."
                }
              />
              {channels.isLoading ? (
                <Skeleton className="h-56 w-full" />
              ) : (
                <HBars rows={(channels.data ?? []).map((c) => ({ label: c.name, n: c.count }))} />
              )}
            </Card>
          </div>

          <SpendCard usage={usage.data} loading={usage.isLoading} days={days} now={now} />
        </>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Panel
// --------------------------------------------------------------------------- //

const SECTIONS = [
  { id: "activity", label: "Activity", icon: BarChart3 },
  { id: "topics", label: "Topics", icon: LayoutGrid },
  { id: "channels", label: "Channels", icon: PlayCircle },
  { id: "spend", label: "Spend", icon: Coins },
];

function InsightsPanel({ range, setRange }: { range: Range; setRange: (r: Range) => void }) {
  const go = (id: string) =>
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  return (
    <PanelSlot title="Insights" sub={RANGES.find((r) => r.id === range)!.long.toLowerCase()}>
      <PanelSection title="Range">
        {RANGES.map((r) => (
          <PanelButton
            key={r.id}
            on={range === r.id}
            onClick={() => setRange(r.id)}
            lead={
              <span
                className={cn(
                  "grid size-4 shrink-0 place-items-center rounded-full border",
                  range === r.id ? "border-ui-current-fg" : "border-border-strong",
                )}
              >
                {range === r.id && <span className="size-2 rounded-full bg-ui-current-fg" />}
              </span>
            }
            label={r.long}
          />
        ))}
      </PanelSection>
      <PanelSection title="Sections">
        {SECTIONS.map((x) => (
          <PanelButton key={x.id} icon={x.icon} label={x.label} onClick={() => go(x.id)} />
        ))}
      </PanelSection>
    </PanelSlot>
  );
}

// --------------------------------------------------------------------------- //
// Pieces
// --------------------------------------------------------------------------- //

/** A whole number that counts up the first time it's seen. */
function CountUp({ n }: { n: number }) {
  const [ref, value] = useCountUp(n);
  return <span ref={ref}>{thousands(value)}</span>;
}

function Kpi({ k, v, d }: { k: string; v: React.ReactNode; d: React.ReactNode }) {
  return (
    <div className="flex flex-col rounded-[14px] border border-border bg-surface px-4 pb-3.5 pt-4">
      <span className="font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-fg-subtle">{k}</span>
      <span className="mt-2 font-display text-[26px] font-semibold leading-none tabular-nums text-fg">{v}</span>
      <span className="mt-2.5 truncate text-[13px] text-fg-muted">{d}</span>
    </div>
  );
}

function Card({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-8 rounded-[14px] border border-border bg-surface px-5 pb-4 pt-5">
      {children}
    </section>
  );
}

function CardHead({
  title,
  sub,
  big,
}: {
  title: string;
  sub?: React.ReactNode;
  big?: { k: string; v: string };
}) {
  return (
    <header className="mb-4 flex items-start gap-4">
      <div className="min-w-0 flex-1">
        <h2 className="font-display text-[17px] font-semibold tracking-[-0.01em]">{title}</h2>
        {sub && <p className="mt-0.5 text-[14px] leading-5 text-fg-muted">{sub}</p>}
      </div>
      {big && (
        <div className="shrink-0 text-right">
          <span className="block font-mono text-[11px] uppercase tracking-[0.08em] text-fg-subtle">{big.k}</span>
          <b className="font-display text-[28px] font-semibold leading-tight tabular-nums">{big.v}</b>
        </div>
      )}
    </header>
  );
}

/** "View as table" — every chart's values, readable without the chart. */
function DataTable({ cols, rows }: { cols: string[]; rows: (string | number)[][] }) {
  if (!rows.length) return null;
  return (
    <details className="mt-3">
      <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 text-[13px] text-fg-subtle hover:text-fg-muted [&::-webkit-details-marker]:hidden">
        <List className="size-3.5" /> View as table
      </summary>
      <div className="mt-2 max-h-64 overflow-y-auto rounded-[10px] border border-border">
        <table className="w-full text-[13px]">
          <thead className="sticky top-0 bg-surface-2">
            <tr>
              {cols.map((c) => (
                <th
                  key={c}
                  className="px-3 py-1.5 text-left font-mono text-[11px] font-medium uppercase tracking-wide text-fg-subtle"
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-border">
                {r.map((c, j) => (
                  <td key={j} className={cn("px-3 py-1.5 text-fg-muted", j > 0 && "font-mono tabular-nums")}>
                    {c}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

const axis = {
  stroke: CHART.axis,
  tick: { fontSize: 11, fill: CHART.axis },
  tickLine: false,
  axisLine: false,
};

type TipProps = { active?: boolean; payload?: { value?: number; payload?: Bucket }[]; label?: string };

function BucketTip({ active, payload, label }: TipProps) {
  if (!active || !payload?.length) return null;
  const b = payload[0].payload;
  return (
    <div className="rounded-md border border-border-strong bg-surface-2 px-3 py-2 text-[12px] shadow-lg">
      <p className="mb-0.5 font-mono text-[11px] text-fg-subtle">{label}</p>
      <p className="text-fg">
        <span className="font-semibold tabular-nums">{thousands(payload[0].value ?? 0)}</span>{" "}
        <span className="text-fg-muted">items</span>
      </p>
      {b?.spike ? <p className="text-fg-muted">+{thousands(b.spike)} in the import</p> : null}
    </div>
  );
}

function ItemsChart({ buckets, spike }: { buckets: Bucket[]; spike: TimelinePoint | null }) {
  const spikeKey = buckets.find((b) => b.spike)?.label;
  return (
    <>
      {spike && (
        <p className="mb-1 font-mono text-[11px] text-fg-subtle">
          ↑ {thousands(spike.count)} imported {shortDate(spike.date)} — marked, left out of the bars
        </p>
      )}
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={buckets} margin={{ top: 8, right: 4, bottom: 0, left: -18 }} barCategoryGap="22%">
          <CartesianGrid stroke={CHART.grid} strokeDasharray="2 4" vertical={false} />
          <XAxis dataKey="label" {...axis} interval="preserveStartEnd" minTickGap={28} />
          <YAxis {...axis} allowDecimals={false} width={44} />
          <Tooltip content={<BucketTip />} cursor={{ fill: CHART.surface }} />
          {spikeKey && <ReferenceLine x={spikeKey} stroke={CHART.axis} strokeDasharray="3 3" />}
          <Bar dataKey="count" fill={CHART.series} radius={[4, 4, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}

type HRow = { label: string; n: number; right?: React.ReactNode; dot?: boolean; muted?: boolean };

/** Labelled horizontal bars: label · bar · value (one series, sky). */
function HBars({ rows, fmt = thousands }: { rows: HRow[]; fmt?: (n: number) => string }) {
  const max = Math.max(1e-9, ...rows.map((r) => r.n));
  return (
    <div className="space-y-1">
      {rows.map((r) => (
        <div
          key={r.label}
          className="group grid grid-cols-[minmax(0,10rem)_minmax(0,1fr)_auto] items-center gap-3 rounded-md px-1 py-1 hover:bg-surface-2/60 sm:grid-cols-[minmax(0,13rem)_minmax(0,1fr)_auto]"
          title={`${r.label}: ${fmt(r.n)}`}
        >
          <span className={cn("flex min-w-0 items-center gap-1.5 text-[14px]", r.muted ? "text-fg-subtle" : "text-fg")}>
            {r.dot && <span className="size-1.5 shrink-0 rounded-full bg-signal" />}
            <span className="truncate">{r.label}</span>
          </span>
          <span className="h-2.5 overflow-hidden">
            <span
              className={cn(
                "m-bar block h-full rounded-r-[3px] transition-colors",
                r.muted ? "bg-ui-chart-track" : "bg-ui-chart-1 group-hover:bg-ui-chart-2",
              )}
              style={{ width: `${Math.max(0.8, (r.n / max) * 100)}%` }}
            />
          </span>
          <span className="whitespace-nowrap text-right font-mono text-[12px] tabular-nums text-fg">
            {fmt(r.n)}
            {r.right}
          </span>
        </div>
      ))}
    </div>
  );
}

function TopicBars({
  topics,
  total,
  unread,
}: {
  topics: { slug: string; label: string; count: number }[];
  total: number;
  unread: Set<string>;
}) {
  const top = topics.slice(0, 7);
  const rest = topics.slice(7);
  const restCount = rest.reduce((s, t) => s + t.count, 0);
  const share = (n: number) => (
    <span className="ml-2.5 inline-block w-10 text-fg-subtle">{pct(n, total)}</span>
  );
  const rows: HRow[] = top.map((t) => ({
    label: t.label,
    n: t.count,
    dot: unread.has(t.slug),
    right: share(t.count),
  }));
  if (rest.length)
    rows.push({
      label: `${rest.length} other topic${rest.length === 1 ? "" : "s"}`,
      n: restCount,
      muted: true,
      right: share(restCount),
    });
  return <HBars rows={rows} />;
}

const SURFACE_LABEL: Record<string, string> = {
  chat: "Chat",
  summarize: "Summaries",
  transcribe: "Transcription",
  classify: "Topic classification",
  discover: "Topic discovery",
};

function SpendCard({
  usage,
  loading,
  days,
  now,
}: {
  usage?: Usage;
  loading: boolean;
  days: number | null;
  now: number;
}) {
  const byDay = useMemo(() => {
    const from = days ? ymd(new Date(now - (days - 1) * DAY)) : "";
    return (usage?.by_day ?? []).filter((d) => d.date >= from);
  }, [usage, days, now]);
  // Per month for all time, per day for the short ranges.
  const series = useMemo(() => {
    const m = new Map<string, number>();
    for (const d of byDay) {
      const k = days ? d.date : d.date.slice(0, 7);
      m.set(k, (m.get(k) ?? 0) + d.cost_usd);
    }
    return [...m.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, cost]) => ({
        key,
        label: days
          ? shortDate(key)
          : new Date(`${key}-01T00:00:00Z`).toLocaleDateString("en-US", {
              month: "short",
              year: "2-digit",
              timeZone: "UTC",
            }),
        cost,
      }));
  }, [byDay, days]);
  const features = useMemo(() => {
    const m = new Map<string, number>();
    for (const d of byDay) m.set(d.surface, (m.get(d.surface) ?? 0) + d.cost_usd);
    const calls = new Map((usage?.by_surface ?? []).map((s) => [s.surface, s.calls]));
    return [...m.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([surface, cost]) => ({ surface, cost, calls: days ? 0 : (calls.get(surface) ?? 0) }));
  }, [byDay, usage, days]);
  const total = byDay.reduce((s, d) => s + d.cost_usd, 0);
  const models = [...(usage?.by_model ?? [])].sort((a, b) => b.cost_usd - a.cost_usd);
  const modelTotal = models.reduce((s, m) => s + m.cost_usd, 0);

  return (
    <Card id="spend">
      <CardHead
        title="LLM spend"
        sub="OpenRouter + Groq — token and transcription cost, tracked only."
        big={{ k: days ? `last ${days} days` : "all time", v: usd(total) }}
      />
      {loading ? (
        <Skeleton className="h-52 w-full" />
      ) : !series.length ? (
        <p className="py-6 text-center text-[14px] text-fg-muted">No spend recorded in this range.</p>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.08em] text-fg-subtle">
              {days ? "Per day" : "Per month"}
            </p>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={series} margin={{ top: 4, right: 4, bottom: 0, left: -6 }} barCategoryGap="28%">
                <CartesianGrid stroke={CHART.grid} strokeDasharray="2 4" vertical={false} />
                <XAxis dataKey="label" {...axis} interval="preserveStartEnd" minTickGap={24} />
                <YAxis {...axis} width={56} tickFormatter={(v: number) => usd(v)} />
                <Tooltip
                  cursor={{ fill: CHART.surface }}
                  content={({ active, payload, label }) =>
                    active && payload?.length ? (
                      <div className="rounded-md border border-border-strong bg-surface-2 px-3 py-2 text-[12px] shadow-lg">
                        <p className="mb-0.5 font-mono text-[11px] text-fg-subtle">{label}</p>
                        <p className="font-semibold tabular-nums text-fg">{usd(Number(payload[0].value ?? 0))}</p>
                      </div>
                    ) : null
                  }
                />
                <Bar dataKey="cost" fill={CHART.series} radius={[4, 4, 0, 0]} maxBarSize={36} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div>
            <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.08em] text-fg-subtle">
              By feature · {days ? `last ${days} days` : "all time"}
            </p>
            <HBars
              rows={features.map((f) => ({
                label: SURFACE_LABEL[f.surface] ?? f.surface,
                n: f.cost,
                right: f.calls ? (
                  <span className="ml-2.5 text-fg-subtle">
                    {thousands(f.calls)} call{f.calls === 1 ? "" : "s"}
                  </span>
                ) : undefined,
              }))}
              fmt={usd}
            />
            {models.length > 0 && modelTotal > 0 && (
              <p className="mt-3 font-mono text-[11px] leading-4 text-fg-subtle">
                by model (all time):{" "}
                {models
                  .slice(0, 3)
                  .map((m) => `${m.model.split("/").pop()} ${Math.round((m.cost_usd / modelTotal) * 100)}%`)
                  .join(" · ")}
              </p>
            )}
          </div>
        </div>
      )}
      <DataTable cols={[days ? "Day" : "Month", "Spend"]} rows={series.map((s) => [s.label, usd(s.cost)])} />
    </Card>
  );
}
