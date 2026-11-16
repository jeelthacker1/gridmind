import { create } from "zustand";
export type Tab =
  | "Control center"
  | "Forecast studio"
  | "What-if lab"
  | "Data & assets"
  | "Reports";
export const useWorkspace = create<{ tab: Tab; setTab: (tab: Tab) => void }>(
  (set) => ({ tab: "Control center", setTab: (tab) => set({ tab }) }),
);
