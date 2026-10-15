import type { Item, ListItem } from "@/lib/api/endpoints";
import { detailRows } from "@/lib/itemDetails";
import { cn } from "@/lib/utils";

/** The item's key/value details card — the Reader's rail and the drawer. */
export function DetailsList({
  item,
  className,
}: {
  item: ListItem & { ingest_usage?: Item["ingest_usage"] };
  className?: string;
}) {
  return (
    <dl className={cn("space-y-2 rounded-[10px] border border-border bg-surface p-4", className)}>
      {detailRows(item).map(([label, value]) => (
        <div key={label} className="flex items-baseline justify-between gap-3">
          <dt className="shrink-0 font-mono text-[10px] uppercase tracking-wide text-fg-subtle">
            {label}
          </dt>
          <dd className="truncate text-right text-[12.5px] text-fg-muted" title={value}>
            {value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
