import { Link } from "react-router-dom";
import { Sparkles, ArrowRight } from "lucide-react";
import { useItems } from "@/hooks/useItems";
import { useTimeline } from "@/hooks/useInsights";
import { useActiveTasks } from "@/store/tasks";
import { useUi } from "@/store/ui";
import { Omnibox } from "@/components/ingest/Omnibox";
import { TaskRow } from "@/components/ingest/TaskRow";
import { ItemGrid } from "@/components/items/ItemGrid";
import { StatTile } from "@/components/common/StatTile";
import { CardGridSkeleton, StatTilesSkeleton } from "@/components/common/Skeletons";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { Button } from "@/components/ui/button";
import { thousands } from "@/lib/format";

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning.";
  if (h < 18) return "Good afternoon.";
  return "Good evening.";
}

function today(): string {
  return new Date()
    .toLocaleDateString("en-US", {
      weekday: "long",
      month: "long",
      day: "numeric",
    })
    .toUpperCase();
}

/** Sum of items ingested within the last 7 calendar days. */
function thisWeek(timeline: { date: string; count: number }[] | undefined): number {
  if (!timeline) return 0;
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - 6);
  cutoff.setHours(0, 0, 0, 0);
  return timeline
    .filter((p) => new Date(p.date) >= cutoff)
    .reduce((sum, p) => sum + p.count, 0);
}

export default function TodayRoute() {
  const recent = useItems({ sort: "newest", per_page: 12 });
  const timeline = useTimeline();
  const activeIds = useActiveTasks((s) => s.activeIds);
  const openAdd = useUi((s) => s.openAdd);

  const total = recent.data?.total ?? 0;
  const isFresh = !recent.isLoading && !recent.isError && total === 0;

  return (
    <div className="space-y-10">
      {/* Hero */}
      <section className="space-y-5">
        <p className="eyebrow">
          {today()} · {recent.isLoading ? "…" : `${thousands(total)} SOURCES`}
        </p>
        <div className="flex max-w-[1200px] flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex-1 space-y-5">
            <h1 className="text-[30px] font-semibold leading-tight">{greeting()}</h1>
            <Omnibox className="max-w-2xl" />
          </div>

          {!isFresh && (
            <div className="grid shrink-0 grid-cols-2 gap-3 lg:w-[300px]">
              {timeline.isLoading || recent.isLoading ? (
                <div className="col-span-2">
                  <StatTilesSkeleton count={2} />
                </div>
              ) : (
                <>
                  <StatTile label="Total" value={thousands(total)} />
                  <StatTile
                    label="This week"
                    value={thousands(thisWeek(timeline.data))}
                    accent
                  />
                </>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Fresh-vault empty state */}
      {isFresh && (
        <EmptyState
          icon={Sparkles}
          title="Your vault is empty"
          description="Paste a YouTube link above, or add your first source to get started."
          action={
            <Button size="sm" onClick={() => openAdd()}>
              Ingest your first source
            </Button>
          }
        />
      )}

      {/* Ingesting (live) */}
      {activeIds.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="eyebrow">Ingesting · {activeIds.length} active</p>
            <Link
              to="/library?sort=newest"
              className="text-[12px] text-fg-muted hover:text-fg"
            >
              View all →
            </Link>
          </div>
          <div className="space-y-2">
            {activeIds.map((id) => (
              <TaskRow key={id} taskId={id} />
            ))}
          </div>
        </section>
      )}

      {/* Recently added */}
      {!isFresh && (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="eyebrow">Recently added</p>
            <Link
              to="/library"
              className="inline-flex items-center gap-1 text-[12px] text-fg-muted hover:text-fg"
            >
              View library <ArrowRight className="size-3.5" />
            </Link>
          </div>

          {recent.isLoading ? (
            <CardGridSkeleton count={8} />
          ) : recent.isError ? (
            <ErrorState error={recent.error} onRetry={() => recent.refetch()} />
          ) : (
            <ItemGrid items={recent.data!.items} density="cozy" view="grid" />
          )}
        </section>
      )}
    </div>
  );
}
