import { create } from "zustand";

interface UiState {
  sidebarCollapsed: boolean;
  commandPaletteOpen: boolean;
  quickCreateOpen: boolean;
  quickCreateKind: QuickCreateKind;
  privacyLocked: boolean;
  toasts: ToastMessage[];
  toggleSidebar: () => void;
  setCommandPaletteOpen: (open: boolean) => void;
  openQuickCreate: (kind?: QuickCreateKind) => void;
  closeQuickCreate: () => void;
  lockPrivacy: () => void;
  unlockPrivacy: () => void;
  pushToast: (message: Omit<ToastMessage, "id">) => void;
  dismissToast: (id: string) => void;
}

export type QuickCreateKind = "event" | "note" | "task" | "transaction";

export interface ToastMessage {
  id: string;
  title: string;
  description?: string;
  tone?: "error" | "success";
}

export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: false,
  commandPaletteOpen: false,
  quickCreateOpen: false,
  quickCreateKind: "task",
  privacyLocked: false,
  toasts: [],
  toggleSidebar: () =>
    set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setCommandPaletteOpen: (commandPaletteOpen) => set({ commandPaletteOpen }),
  openQuickCreate: (quickCreateKind = "task") =>
    set({ quickCreateOpen: true, quickCreateKind }),
  closeQuickCreate: () => set({ quickCreateOpen: false }),
  lockPrivacy: () => set({ privacyLocked: true, commandPaletteOpen: false, quickCreateOpen: false }),
  unlockPrivacy: () => set({ privacyLocked: false }),
  pushToast: (message) =>
    set((state) => ({
      toasts: [
        ...state.toasts,
        { ...message, id: crypto.randomUUID() },
      ].slice(-4),
    })),
  dismissToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) })),
}));
