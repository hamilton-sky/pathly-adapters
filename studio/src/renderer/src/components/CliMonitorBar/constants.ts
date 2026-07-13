import type { EngineAdapter, EngineCategory, EngineStatus, Stage } from './types'

// Visual language for the dock. All colors resolve to design-system tokens; the only
// hex values are host-CLI brand accents (injected as a --adapter custom property).

export const CATEGORY_ORDER: EngineCategory[] = ['flow', 'loop', 'single']

export function categoryColor(cat: EngineCategory): string {
  return { flow: 'var(--accent)', loop: 'var(--purple)', single: 'var(--runtime)' }[cat]
}

export const ADAPTER_COLOR: Record<EngineAdapter, string> = {
  Claude: '#D97706',
  Codex:  '#2563EB',
  Gemini: '#16A34A',
}

export function statusColor(st: EngineStatus): string {
  return { running: 'var(--runtime)', queued: 'var(--text-muted)', done: 'var(--green)', failed: 'var(--red)' }[st]
}

export function stageColor(stage: Stage | string): string {
  const map: Record<string, string> = {
    PLANNING: 'var(--text-muted)',
    BUILDING: 'var(--blue)',
    REVIEWING: 'var(--orange)',
    TESTING: 'var(--purple)',
    RETRO: 'var(--runtime)',
    DONE: 'var(--green)',
  }
  return map[stage] ?? 'var(--purple)'
}

/** How many concurrent headless engines the runner allows. */
export const MAX_SLOTS = 5
