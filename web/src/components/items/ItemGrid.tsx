import type { ListItem } from "@/lib/api/endpoints";
import { ItemCard, ItemRow } from "./ItemCard";
import type { Density, LibraryView } from "@/store/ui";

// Density → grid track min-width + gap (DESIGN_SYSTEM §4).
const DENSITY: Record<Density, { min: number; gap: string; dense: boolean }> = {
  comfortable: { min: 320, gap: "gap-5", dense: false },
  cozy: { min: 280, gap: "gap-4", dense: false },
  compact: { min: 220, gap: "gap-3", dense: true },
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
      className={d.gap}
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(auto-fill, minmax(${d.min}px, 1fr))`,
      }}
    >
      {items.map((it) => (
        <ItemCard
          key={it.id}
          item={it}
          dense={d.dense}
          highlight={highlight}
          focused={it.id === focusedId}
        />
      ))}
    </div>
  );
}
