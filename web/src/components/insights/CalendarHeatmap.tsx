import { useMemo } from "react";

type Point = { date: string; count: number };

// Fixed thresholds (not max-relative) so a single bulk-import day doesn't wash
// out ordinary daily activity — the old area chart's failure mode.
const LEVEL_FILL = [
  "var(--color-surface-2)",
  "rgba(255,75,75,0.28)",
  "rgba(255,75,75,0.48)",
  "rgba(255,75,75,0.72)",
  "#ff4b4b",
];
function level(count: number): number {
  if (count <= 0) return 0;
  if (count >= 20) return 4;
  if (count >= 8) return 3;
  if (count >= 3) return 2;
  return 1;
}

const MS_DAY = 86_400_000;
const dayKey = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate(),
  ).padStart(2, "0")}`;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/**
 * GitHub-style contribution grid: one square per day, weeks as columns. Far more
 * legible than a line chart for sparse, spiky daily ingest counts.
 */
export function CalendarHeatmap({ data }: { data: Point[] }) {
  const { weeks, monthLabels } = useMemo(() => buildGrid(data), [data]);

  return (
    <div className="overflow-x-auto">
      <div className="inline-flex flex-col gap-1.5">
        {/* Month labels */}
        <div className="flex gap-[3px] pl-[2px] text-[10px] text-fg-subtle">
          {weeks.map((_week, i) => (
            <div key={i} className="w-[13px] font-mono">
              {monthLabels[i] ?? ""}
            </div>
          ))}
        </div>
        {/* Day grid: 7 rows, weeks as columns */}
        <div
          className="grid grid-flow-col gap-[3px]"
          style={{ gridTemplateRows: "repeat(7, 13px)" }}
        >
          {weeks.flatMap((week) =>
            week.map((cell, di) =>
              cell ? (
                <div
                  key={cell.key}
                  className="size-[13px] rounded-[3px]"
                  style={{ backgroundColor: LEVEL_FILL[level(cell.count)] }}
                  title={`${cell.label} · ${cell.count} ${cell.count === 1 ? "item" : "items"}`}
                />
              ) : (
                <div key={`pad-${di}-${Math.random()}`} className="size-[13px]" />
              ),
            ),
          )}
        </div>
        {/* Legend */}
        <div className="flex items-center gap-1.5 pt-1 text-[10px] text-fg-subtle">
          <span>Less</span>
          {LEVEL_FILL.map((fill, i) => (
            <span
              key={i}
              className="size-[11px] rounded-[3px]"
              style={{ backgroundColor: fill }}
            />
          ))}
          <span>More</span>
        </div>
      </div>
    </div>
  );
}

type Cell = { key: string; count: number; label: string } | null;

function buildGrid(data: Point[]): { weeks: Cell[][]; monthLabels: (string | null)[] } {
  const counts = new Map<string, number>();
  let min: Date | null = null;
  for (const p of data) {
    const d = new Date(p.date);
    if (Number.isNaN(d.getTime())) continue;
    const key = dayKey(d);
    counts.set(key, (counts.get(key) ?? 0) + p.count);
    if (!min || d < min) min = d;
  }

  const today = new Date();
  const end = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  // Default to ~6 months back if there's no data.
  const start = min
    ? new Date(min.getFullYear(), min.getMonth(), min.getDate())
    : new Date(end.getTime() - 182 * MS_DAY);
  // Snap the start back to the most recent Sunday so column 0 begins a week.
  start.setDate(start.getDate() - start.getDay());

  const weeks: Cell[][] = [];
  const monthLabels: (string | null)[] = [];
  let cursor = new Date(start);
  let lastMonth = -1;

  while (cursor <= end) {
    const week: Cell[] = [];
    let labelForWeek: string | null = null;
    for (let day = 0; day < 7; day++) {
      if (cursor > end) {
        week.push(null);
        continue;
      }
      const key = dayKey(cursor);
      const m = cursor.getMonth();
      if (day === 0 && m !== lastMonth) {
        labelForWeek = MONTHS[m];
        lastMonth = m;
      }
      week.push({
        key,
        count: counts.get(key) ?? 0,
        label: cursor.toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
        }),
      });
      cursor = new Date(cursor.getTime() + MS_DAY);
    }
    weeks.push(week);
    monthLabels.push(labelForWeek);
  }

  return { weeks, monthLabels };
}
