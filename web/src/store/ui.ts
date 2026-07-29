import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Density = "comfortable" | "cozy" | "compact";
export type LibraryView = "grid" | "list";

/** A pending "this is already ingested — redo the summary?" confirmation. */
export type ResummarizePrompt = {
  itemId: string;
  title: string | null;
  summary_length: string;
  languages: string[];
};

type UiState = {
  // Command palette
  paletteOpen: boolean;
  setPaletteOpen: (open: boolean) => void;
  // Add-source dialog (global overlay)
  addOpen: boolean;
  addPrefill: string;
  openAdd: (prefill?: string) => void;
  setAddOpen: (open: boolean) => void;
  // Re-summarise confirmation: set when an ingest hits an already-ingested
  // video, so a global dialog can ask the user before redoing the summary.
  resummarizePrompt: ResummarizePrompt | null;
  openResummarizePrompt: (p: ResummarizePrompt) => void;
  closeResummarizePrompt: () => void;
  // Library view prefs (persisted)
  density: Density;
  view: LibraryView;
  setDensity: (d: Density) => void;
  setView: (v: LibraryView) => void;
  cycleDensity: () => void;
  // Pinned chat threads (persisted) — frontend-only favouriting; pinned ids sort
  // to a "Pinned" group at the top of the conversation sidebar.
  pinnedThreads: string[];
  togglePin: (id: string) => void;
  // Per-thread composer drafts (session-only, NOT persisted). The chat pane is
  // keyed by thread id and remounts on switch, which would otherwise drop
  // typed-but-unsent input; this map carries it across switches.
  chatDrafts: Record<string, string>;
  setChatDraft: (id: string, text: string) => void;
  clearChatDraft: (id: string) => void;
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

      resummarizePrompt: null,
      openResummarizePrompt: (p) => set({ resummarizePrompt: p }),
      closeResummarizePrompt: () => set({ resummarizePrompt: null }),

      density: "cozy",
      view: "grid",
      setDensity: (density) => set({ density }),
      setView: (view) => set({ view }),
      cycleDensity: () => {
        const i = DENSITY_ORDER.indexOf(get().density);
        set({ density: DENSITY_ORDER[(i + 1) % DENSITY_ORDER.length] });
      },

      pinnedThreads: [],
      togglePin: (id) =>
        set((s) => ({
          pinnedThreads: s.pinnedThreads.includes(id)
            ? s.pinnedThreads.filter((x) => x !== id)
            : [...s.pinnedThreads, id],
        })),

      chatDrafts: {},
      setChatDraft: (id, text) =>
        set((s) => ({ chatDrafts: { ...s.chatDrafts, [id]: text } })),
      clearChatDraft: (id) =>
        set((s) => {
          if (!(id in s.chatDrafts)) return s;
          const next = { ...s.chatDrafts };
          delete next[id];
          return { chatDrafts: next };
        }),
    }),
    {
      name: "merlin-ui",
      // Drafts are deliberately omitted — they're ephemeral session state.
      partialize: (s) => ({
        density: s.density,
        view: s.view,
        pinnedThreads: s.pinnedThreads,
      }),
    },
  ),
);
