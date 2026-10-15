import { create } from 'zustand'

/** The composer popover's tabs: what the next HQ question carries. */
export type HqScopeTab = 'context' | 'actions'

/** Which composer popover tab is open, if any. Shared so an answer's context
 *  line ("Adjust for next question") can open the popover the chip row owns.
 *  Not persisted — the popover always starts closed. */
interface HqComposerState {
  openTab: HqScopeTab | null
  openScope: (tab: HqScopeTab) => void
  closeScope: () => void
}

export const useHqComposerStore = create<HqComposerState>()((set) => ({
  openTab: null,
  openScope: (tab) => set({ openTab: tab }),
  closeScope: () => set({ openTab: null }),
}))
