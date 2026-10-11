import type { ListItem } from "@/lib/api/endpoints";
import { ItemCard, ItemRow } from "./ItemCard";
import type { Density, LibraryView } from "@/store/ui";

// Density → grid track min-width (≥ sm) + what the card shows. Phones always
// get two columns (mockup), whatever the density.
const DENSITY: Record<Density, { min: number; dense: boolean; snippet: boolean }> = {
  comfortable: { min: 300, dense: false, snippet: true },
  cozy: { min: 250, dense: false, snippet: false },
  compact: { min: 200, dense: true, snippet: false },
};

export function ItemGrid({
  items,
  density = "cozy",
  view = "grid",
  highlight,
  focusedId,
}: {
  items: ListItem[];
  density?: Density;
  view?: LibraryView;
  /** Search term to highlight in titles/snippets. */
  highlight?: string;
  /** Item id currently focused via keyboard (j/k). */
  focusedId?: string;
}) {
  if (view === "list") {
    return (
      <div className="flex flex-col gap-2">
        {items.map((it) => (
          <ItemRow
            key={it.id}
            item={it}
            highlight={highlight}
            focused={it.id === focusedId}
          />
        ))}
      </div>
    );
  }

  const d = DENSITY[density];
  return (
    <div
      className="m-grid grid grid-cols-2 gap-x-3 gap-y-4 sm:grid-cols-[repeat(auto-fill,minmax(var(--card-min),1fr))] sm:gap-x-[18px] sm:gap-y-[22px]"
      style={{ "--card-min": `${d.min}px` } as React.CSSProperties}
    >
      {items.map((it) => (
        <ItemCard
          key={it.id}
          item={it}
          dense={d.dense}
          snippet={d.snippet}
          highlight={highlight}
          focused={it.id === focusedId}
        />
      ))}
    </div>
  );
}
