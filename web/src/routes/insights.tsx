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
} from "@/hooks/useInsights";
import { StatTile } from "@/components/common/StatTile";
import { CalendarHeatmap } from "@/components/insights/CalendarHeatmap";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { thousands } from "@/lib/format";

const COLORS = {
  accent: "#ff4b4b",
  grid: "#232327",
  axis: "#6b6b73",
  surface: "#18181b",
  border: "#2e2e33",
};
const STATUS_COLORS: Record<string, string> = {
  completed: "#30a46c",
  processing: "#5b9df9",
  pending: "#f5a524",
  queued: "#6b6b73",
  failed: "#ff4b4b",
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

export default function InsightsRoute() {
  const timeline = useTimeline();
  const channels = useTopChannels(12);
  const status = useStatusCounts();
  const channelCount = useChannelCount();

  const loading =
    timeline.isLoading || channels.isLoading || status.isLoading || channelCount.isLoading;
  const error = timeline.error || channels.error || status.error || channelCount.error;

  if (error) {
    return (
      <div className="space-y-5">
        <h1 className="text-[24px] font-semibold">Insights</h1>
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
        <h1 className="text-[24px] font-semibold">Insights</h1>
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
                <StatTile label="Failed" value={thousands(failed)} accent={failed > 0} />
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
                  <Bar dataKey="count" name="items" fill={COLORS.accent} radius={[0, 4, 4, 0]} />
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
    </div>
  );
}
