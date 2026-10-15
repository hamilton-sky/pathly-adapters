import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/** The board sections HQ can feed the local model — mirrors the server's
 *  hq_context.SECTION_NAMES, in display order, with the default choice
 *  (SECTION_DEFAULTS: artifact summaries are opt-in). */
export const HQ_SECTIONS = [
  { name: 'questions', label: 'Pending questions', defaultOn: true },
  { name: 'runs', label: 'Runs', defaultOn: true },
  { name: 'goals', label: 'Goals & progress', defaultOn: true },
  { name: 'events', label: 'Recent events', defaultOn: true },
  { name: 'artifacts', label: 'Artifact titles', defaultOn: true },
  { name: 'summaries', label: 'Artifact summaries', defaultOn: false },
] as const

export type HqSectionName = (typeof HQ_SECTIONS)[number]['name']

const DEFAULTS = Object.fromEntries(HQ_SECTIONS.map((s) => [s.name, s.defaultOn])) as Record<HqSectionName, boolean>

/** Saved choice of which sections go into the next HQ question. */
interface HqContextState {
  enabled: Record<HqSectionName, boolean>
  toggle: (name: HqSectionName) => void
  /** Back to the server's SECTION_DEFAULTS. */
  reset: () => void
}

export const useHqContextStore = create<HqContextState>()(
  persist(
    (set) => ({
      enabled: DEFAULTS,
      toggle: (name) => set((s) => ({ enabled: { ...s.enabled, [name]: !s.enabled[name] } })),
      reset: () => set({ enabled: DEFAULTS }),
    }),
    {
      name: 'pathly-hq-context',
      // A section added later starts at its default instead of undefined.
      merge: (persisted, current) => ({
        ...current,
        enabled: { ...DEFAULTS, ...((persisted as Partial<HqContextState>)?.enabled ?? {}) },
      }),
    },
  ),
)

/** Whether the choice is the default one (the Defaults button hides then). */
export function isDefaultHqSections(enabled: Record<HqSectionName, boolean>): boolean {
  return HQ_SECTIONS.every((s) => enabled[s.name] === s.defaultOn)
}

/** The sections the next question carries, in display order. */
export function selectedHqSections(
  enabled: Record<HqSectionName, boolean> = useHqContextStore.getState().enabled,
): HqSectionName[] {
  return HQ_SECTIONS.filter((s) => enabled[s.name]).map((s) => s.name)
}

/** Friendly label for a section name ("questions" → "Pending questions"). */
export function hqSectionLabel(name: string): string {
  return HQ_SECTIONS.find((s) => s.name === name)?.label ?? name
}

export function isHqSectionName(name: string): name is HqSectionName {
  return HQ_SECTIONS.some((s) => s.name === name)
}
