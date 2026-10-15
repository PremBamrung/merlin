import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Density = "comfortable" | "cozy" | "compact";
export type LibraryView = "grid" | "list";
/** An explicit open/closed choice for the context panel; `null` = automatic
 *  (open from 1280px, collapsed below — the approved default). */
export type PanelPref = "open" | "closed" | null;
/** Chat thinking level, sent with every chat message (LiteLLM only — the
 *  composer hides the picker when the backend can't honour it). */
export type ThinkingLevel = "minimal" | "low" | "medium" | "high";

/** A pending "this is already ingested — redo the summary?" confirmation. */
export type ResummarizePrompt = {
  itemId: string;
  title: string | null;
  summary_length: string;
  languages: string[];
};

type UiState = {
  // Context panel (desktop column; persisted) + its mobile drawer (session).
  panelPref: PanelPref;
  setPanelPref: (p: PanelPref) => void;
  drawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;
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
  // Chat thinking level (persisted) — shared by the chat page and Reader chat.
  thinking: ThinkingLevel;
  setThinking: (t: ThinkingLevel) => void;
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
      panelPref: null,
      setPanelPref: (panelPref) => set({ panelPref }),
      drawerOpen: false,
      setDrawerOpen: (drawerOpen) => set({ drawerOpen }),

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

      thinking: "medium",
      setThinking: (thinking) => set({ thinking }),

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
        panelPref: s.panelPref,
        thinking: s.thinking,
      }),
    },
  ),
);
