import { Skeleton } from "@/components/ui/skeleton";

/** A single item-card skeleton — mirrors ItemCard (thumbnail, two title
 *  lines, the meta line). */
export function ItemCardSkeleton() {
  return (
    <div>
      <Skeleton className="aspect-video w-full rounded-[10px]" />
      <div className="space-y-2 px-0.5 pt-3">
        <Skeleton className="h-3.5 w-11/12" />
        <Skeleton className="h-3.5 w-3/5" />
        <Skeleton className="h-2.5 w-2/5" />
      </div>
    </div>
  );
}

/** A grid of card skeletons, on the same tracks as ItemGrid. */
export function CardGridSkeleton({ count = 8 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 gap-x-3 gap-y-4 sm:grid-cols-[repeat(auto-fill,minmax(250px,1fr))] sm:gap-x-[18px] sm:gap-y-[22px]">
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
