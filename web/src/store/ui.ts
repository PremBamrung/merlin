import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Density = "comfortable" | "cozy" | "compact";
export type LibraryView = "grid" | "list";

type UiState = {
  // Command palette
  paletteOpen: boolean;
  setPaletteOpen: (open: boolean) => void;
  // Add-source dialog (global overlay)
  addOpen: boolean;
  addPrefill: string;
  openAdd: (prefill?: string) => void;
  setAddOpen: (open: boolean) => void;
  // Mobile navigation drawer (only rendered below the `md` breakpoint)
  navOpen: boolean;
  setNavOpen: (open: boolean) => void;
  // Library view prefs (persisted)
  density: Density;
  view: LibraryView;
  setDensity: (d: Density) => void;
  setView: (v: LibraryView) => void;
  cycleDensity: () => void;
};

const DENSITY_ORDER: Density[] = ["comfortable", "cozy", "compact"];

export const useUi = create<UiState>()(
  persist(
    (set, get) => ({
      paletteOpen: false,
      setPaletteOpen: (open) => set({ paletteOpen: open }),

      addOpen: false,
      addPrefill: "",
      openAdd: (prefill = "") => set({ addOpen: true, addPrefill: prefill }),
      setAddOpen: (open) => set({ addOpen: open }),

      navOpen: false,
      setNavOpen: (open) => set({ navOpen: open }),

      density: "cozy",
      view: "grid",
      setDensity: (density) => set({ density }),
      setView: (view) => set({ view }),
      cycleDensity: () => {
        const i = DENSITY_ORDER.indexOf(get().density);
        set({ density: DENSITY_ORDER[(i + 1) % DENSITY_ORDER.length] });
      },
    }),
    {
      name: "merlin-ui",
      partialize: (s) => ({ density: s.density, view: s.view }),
    },
  ),
);
