import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/** At most this many actions for one question — the server enforces the same cap. */
export const MAX_HQ_ACTIONS = 8

/** The composer's ticked operator actions: what the NEXT HQ question may
 *  propose (local-operator). Off by default; global, not per board. Only names
 *  Settings makes available are ever sent (useActionSelection filters). */
interface HqActionsState {
  enabled: string[]
  /** Tick or untick one. Ticking past the cap is ignored — never auto-untick. */
  toggle: (name: string) => void
  /** Add a preset's actions, up to the cap, keeping what is already ticked. */
  addMany: (names: string[]) => void
  clear: () => void
}

export const useHqActionsStore = create<HqActionsState>()(
  persist(
    (set) => ({
      enabled: [],
      toggle: (name) =>
        set((s) => {
          if (s.enabled.includes(name)) return { enabled: s.enabled.filter((n) => n !== name) }
          if (s.enabled.length >= MAX_HQ_ACTIONS) return s
          return { enabled: [...s.enabled, name] }
        }),
      addMany: (names) =>
        set((s) => {
          const next = [...s.enabled]
          for (const n of names) {
            if (next.length >= MAX_HQ_ACTIONS) break
            if (!next.includes(n)) next.push(n)
          }
          return { enabled: next }
        }),
      clear: () => set({ enabled: [] }),
    }),
    { name: 'pathly-hq-actions' },
  ),
)
