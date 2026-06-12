import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";

/** A single item-card skeleton — mirrors ItemCard's layout. */
export function ItemCardSkeleton() {
  return (
    <Card className="overflow-hidden">
      <Skeleton className="aspect-video w-full rounded-none" />
      <div className="space-y-2 p-3">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-3 w-1/2" />
      </div>
    </Card>
  );
}

/** A responsive grid of card skeletons. */
export function CardGridSkeleton({ count = 8 }: { count?: number }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <ItemCardSkeleton key={i} />
      ))}
    </div>
  );
}

/** Reader skeleton — title + meta + prose blocks. */
export function ReaderSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
      <div className="space-y-3 pt-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-4" style={{ width: `${70 + ((i * 7) % 30)}%` }} />
        ))}
      </div>
    </div>
  );
}

/** Stat-tile skeletons row. */
export function StatTilesSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <Card key={i} className="p-5">
          <Skeleton className="mb-3 h-3 w-16" />
          <Skeleton className="h-8 w-12" />
        </Card>
      ))}
    </div>
  );
}
