import { create } from 'zustand'

interface UIState {
  addSourceOpen: boolean
  setAddSourceOpen: (open: boolean) => void
  sidebarCollapsed: boolean
  toggleSidebar: () => void
}

export const useUIStore = create<UIState>((set) => ({
  addSourceOpen: false,
  setAddSourceOpen: (open) => set({ addSourceOpen: open }),
  sidebarCollapsed: false,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
}))
