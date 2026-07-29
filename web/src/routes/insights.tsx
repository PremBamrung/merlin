import {
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { BarChart3 } from "lucide-react";
import {
  useTimeline,
  useTopChannels,
  useStatusCounts,
  useChannelCount,
  useUsage,
} from "@/hooks/useInsights";
import type { Usage } from "@/lib/api/endpoints";
import { StatTile } from "@/components/common/StatTile";
import { CalendarHeatmap } from "@/components/insights/CalendarHeatmap";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { thousands } from "@/lib/format";

// Chart chrome, on the new tokens: grid = rule, axis = fg-subtle, cursor/stroke
// = surface-2. `series` is categorical slot 1 (see SURFACE_COLORS) rather than
// the interface accent — #4a60d6 is tuned to be the darkest legal *fill*, which
// is not what a data mark on a grid wants.
const COLORS = {
  series: "#5c82da",
  grid: "#393b41",
  axis: "#8e8e98",
  surface: "#2c2e33",
  border: "#4a4c54",
};
/**
 * Status is a **reserved** scale: green = done, gold = running, indigo = waiting
 * on us, grey = waiting in line, rust = broken. Never reused as "series N".
 * Rust and green are ΔE 4.7 apart under deuteranopia, which is why both charts
 * below render a named legend — colour alone never distinguishes failed from
 * completed.
 */
const STATUS_COLORS: Record<string, string> = {
  completed: "#4fa97a",
  processing: "#ffb94a",
  pending: "#96a5f5",
  queued: "#8e8e98",
  failed: "#d4705a",
};

type TooltipEntry = { value?: number; name?: string };
function ChartTooltip(props: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string | number;
}) {
  const { active, payload, label } = props;
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-border-strong bg-surface-2 px-3 py-2 text-[12px] shadow-lg">
      {label !== undefined && label !== "" && (
        <p className="mb-0.5 font-mono text-[11px] text-fg-subtle">{label}</p>
      )}
      {payload.map((p, i) => (
        <p key={i} className="text-fg">
          <span className="font-semibold tabular-nums">{thousands(p.value ?? 0)}</span>{" "}
          <span className="text-fg-muted">{p.name}</span>
        </p>
      ))}
    </div>
  );
}

function ChartCard({
  title,
  children,
  loading,
}: {
  title: string;
  children: React.ReactNode;
  loading?: boolean;
}) {
  return (
    <Card className="p-5">
      <p className="eyebrow mb-4">{title}</p>
      {loading ? <Skeleton className="h-64 w-full" /> : children}
    </Card>
  );
}

/**
 * Categorical slots for the stacked spend bar, in **stacking order** — the order
 * is the colourblind-safety mechanism, so don't re-shuffle it. Stepped into the
 * dark-mode lightness band (OKLCH L 0.48–0.67) on Merlin's ground and validated:
 * all five clear the chroma floor and 3:1 vs #1a1b1f, worst adjacent pair is
 * ΔE 9.2 under deuteranopia / 21.4 normal. Re-run the check before touching a
 * value (skills/dataviz `validate_palette.js --mode dark --surface "#1a1b1f"`).
 */
const SURFACE_COLORS: Record<string, string> = {
  chat: "#5c82da",
  summarize: "#b98a00",
  transcribe: "#13a5b2",
  classify: "#b93c8c",
  discover: "#429c5a",
};
const SURFACE_ORDER = ["chat", "summarize", "transcribe", "classify", "discover"];

function usd(n: number): string {
  if (!n) return "$0.00";
  if (n < 0.01) return "$" + n.toFixed(4);
  return "$" + n.toFixed(2);
}

function SpendTooltip(props: { active?: boolean; payload?: TooltipEntry[]; label?: string | number }) {
  const { active, payload, label } = props;
  if (!active || !payload?.length) return null;
  const rows = payload.filter((p) => (p.value ?? 0) > 0);
  if (!rows.length) return null;
  return (
    <div className="rounded-md border border-border-strong bg-surface-2 px-3 py-2 text-[12px] shadow-lg">
      <p className="mb-0.5 font-mono text-[11px] text-fg-subtle">{label}</p>
      {rows.map((p, i) => (
        <p key={i} className="text-fg">
          <span className="font-semibold tabular-nums">{usd(p.value ?? 0)}</span>{" "}
          <span className="capitalize text-fg-muted">{p.name}</span>
        </p>
      ))}
    </div>
  );
}

function SpendSection({ usage, loading }: { usage?: Usage; loading: boolean }) {
  const total = usage?.total;
  const bySurface = usage?.by_surface ?? [];
  const surfaces = SURFACE_ORDER.filter((s) => bySurface.some((r) => r.surface === s));
  // Pivot [{date,surface,cost}] → one row per day with a column per surface.
  const days = Array.from(new Set((usage?.by_day ?? []).map((d) => d.date))).sort();
  const daily = days.map((date) => {
    const row: Record<string, number | string> = { date };
    for (const s of surfaces) {
      row[s] = (usage?.by_day ?? [])
        .filter((d) => d.date === date && d.surface === s)
        .reduce((acc, d) => acc + d.cost_usd, 0);
    }
    return row;
  });

  const hasSpend = (total?.calls ?? 0) > 0;

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <h2 className="font-display text-[18px] font-semibold">Spend</h2>
        <span className="eyebrow pb-0.5">Token &amp; transcription cost — tracking only</span>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-5">
              <Skeleton className="mb-3 h-3 w-16" />
              <Skeleton className="h-8 w-12" />
            </Card>
          ))
        ) : (
          <>
            <StatTile label="Total cost" value={usd(total?.cost_usd ?? 0)} />
            <StatTile label="Tokens in" value={thousands(total?.tokens_in ?? 0)} />
            <StatTile label="Tokens out" value={thousands(total?.tokens_out ?? 0)} />
            <StatTile label="Calls" value={thousands(total?.calls ?? 0)} />
          </>
        )}
      </div>

      {!loading && !hasSpend ? (
        <EmptyState
          icon={BarChart3}
          title="No spend recorded yet"
          description="Costs appear here after your next chat or ingest."
        />
      ) : (
        <ChartCard title="Daily cost by surface" loading={loading}>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={daily} margin={{ top: 0, right: 12, bottom: 0, left: 8 }}>
              <CartesianGrid stroke={COLORS.grid} vertical={false} />
              <XAxis
                dataKey="date"
                stroke={COLORS.axis}
                tick={{ fontSize: 11, fill: COLORS.axis }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: string) => v.slice(5)}
              />
              <YAxis
                stroke={COLORS.axis}
                tick={{ fontSize: 11, fill: COLORS.axis }}
                tickLine={false}
                axisLine={false}
                width={56}
                tickFormatter={(v: number) => usd(v)}
              />
              <Tooltip content={<SpendTooltip />} cursor={{ fill: COLORS.surface }} />
              {surfaces.map((s, i) => (
                <Bar
                  key={s}
                  dataKey={s}
                  name={s}
                  stackId="cost"
                  fill={SURFACE_COLORS[s] ?? COLORS.axis}
                  radius={i === surfaces.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
          <div className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1">
            {bySurface.map((s) => (
              <span key={s.surface} className="flex items-center gap-1.5 text-[12px]">
                <span
                  className="size-2 rounded-full"
                  style={{ background: SURFACE_COLORS[s.surface] ?? COLORS.axis }}
                />
                <span className="capitalize text-fg-muted">{s.surface}</span>
                <span className="font-mono tabular-nums text-fg-subtle">{usd(s.cost_usd)}</span>
              </span>
            ))}
          </div>
        </ChartCard>
      )}
    </div>
  );
}

export default function InsightsRoute() {
  const timeline = useTimeline();
  const channels = useTopChannels(12);
  const status = useStatusCounts();
  const channelCount = useChannelCount();
  const usage = useUsage();

  const loading =
    timeline.isLoading || channels.isLoading || status.isLoading || channelCount.isLoading;
  const error = timeline.error || channels.error || status.error || channelCount.error;

  if (error) {
    return (
      <div className="space-y-5">
        <h1 className="font-display text-[24px] font-semibold">Insights</h1>
        <ErrorState
          error={error}
          onRetry={() => {
            timeline.refetch();
            channels.refetch();
            status.refetch();
            channelCount.refetch();
          }}
        />
      </div>
    );
  }

  const statusData = status.data ?? [];
  const total = statusData.reduce((s, r) => s + r.count, 0);
  const failed = statusData.find((r) => r.name === "failed")?.count ?? 0;
  const mostInDay = Math.max(0, ...(timeline.data ?? []).map((p) => p.count));

  const isEmpty = !loading && total === 0;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <h1 className="font-display text-[24px] font-semibold">Insights</h1>
        <span className="eyebrow pb-1">How your library has grown</span>
      </div>

      {isEmpty ? (
        <EmptyState
          icon={BarChart3}
          title="Not enough data yet"
          description="Ingest a few more sources and trends will show up here."
        />
      ) : (
        <>
          {/* Stat tiles */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {loading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <Card key={i} className="p-5">
                  <Skeleton className="mb-3 h-3 w-16" />
                  <Skeleton className="h-8 w-12" />
                </Card>
              ))
            ) : (
              <>
                <StatTile label="Total" value={thousands(total)} />
                <StatTile label="Channels" value={thousands(channelCount.data?.count ?? 0)} />
                <StatTile label="Most in a day" value={thousands(mostInDay)} />
                <StatTile
                  label="Failed"
                  value={thousands(failed)}
                  tone={failed > 0 ? "fail" : "default"}
                />
              </>
            )}
          </div>

          {/* Timeline */}
          <ChartCard title="Ingest activity" loading={loading}>
            <CalendarHeatmap data={timeline.data ?? []} />
          </ChartCard>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {/* Top channels */}
            <ChartCard title="Top channels" loading={loading}>
              <ResponsiveContainer width="100%" height={320}>
                <BarChart
                  data={channels.data ?? []}
                  layout="vertical"
                  margin={{ top: 0, right: 12, bottom: 0, left: 8 }}
                >
                  <CartesianGrid stroke={COLORS.grid} horizontal={false} />
                  <XAxis
                    type="number"
                    stroke={COLORS.axis}
                    tick={{ fontSize: 11, fill: COLORS.axis }}
                    tickLine={false}
                    axisLine={false}
                    allowDecimals={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    stroke={COLORS.axis}
                    tick={{ fontSize: 11, fill: COLORS.axis }}
                    tickLine={false}
                    axisLine={false}
                    width={120}
                    tickFormatter={(v: string) => (v.length > 16 ? v.slice(0, 15) + "…" : v)}
                  />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: COLORS.surface }} />
                  <Bar dataKey="count" name="items" fill={COLORS.series} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            {/* Status donut */}
            <ChartCard title="Status breakdown" loading={loading}>
              <ResponsiveContainer width="100%" height={232}>
                <PieChart>
                  <Pie
                    data={statusData}
                    dataKey="count"
                    nameKey="name"
                    innerRadius={52}
                    outerRadius={84}
                    paddingAngle={2}
                    stroke={COLORS.surface}
                  >
                    {statusData.map((s) => (
                      <Cell
                        key={s.name}
                        fill={STATUS_COLORS[s.name] ?? COLORS.axis}
                      />
                    ))}
                  </Pie>
                  <Tooltip content={<ChartTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1">
                {statusData.map((s) => (
                  <span key={s.name} className="flex items-center gap-1.5 text-[12px]">
                    <span
                      className="size-2 rounded-full"
                      style={{ background: STATUS_COLORS[s.name] ?? COLORS.axis }}
                    />
                    <span className="capitalize text-fg-muted">{s.name}</span>
                    <span className="font-mono tabular-nums text-fg-subtle">{s.count}</span>
                  </span>
                ))}
              </div>
            </ChartCard>
          </div>
        </>
      )}

      <SpendSection usage={usage.data} loading={usage.isLoading} />
    </div>
  );
}
