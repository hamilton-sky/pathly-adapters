import type { EngineAdapter, EngineCategory, EngineStatus, Stage } from './types'

// Single source of truth for the Monitor's visual language. All colors resolve to
// design-system CSS variables — never hand-picked. Category is the core grouping;
// stage colors mirror the shipped FSM palette (PLANNING gray → DONE green).

export interface CategoryMeta {
  key: EngineCategory
  label: string        // section heading, Title Case
  blurb: string        // muted mono sub-label
  /** CSS var for the category color. */
  color: string
}

/** Ordered — this is also the section render order in the board. */
export const CATEGORY_META: CategoryMeta[] = [
  { key: 'flow',   label: 'Flow runs',    blurb: 'full FSM pipeline runs',        color: 'var(--accent)' },
  { key: 'loop',   label: 'Loop cycles',  blurb: 'iterative debug / explore cycles', color: 'var(--purple)' },
  { key: 'single', label: 'Single shots', blurb: 'one-shot editor & board actions',  color: 'var(--runtime)' },
]

export function categoryColor(cat: EngineCategory): string {
  return CATEGORY_META.find((c) => c.key === cat)?.color ?? 'var(--text-muted)'
}

/** Brand-side adapter accent (hex — these are host-tool brand colors, not DS tokens). */
export const ADAPTER_COLOR: Record<EngineAdapter, string> = {
  Claude: '#D97706',
  Codex:  '#2563EB',
  Gemini: '#16A34A',
}

export const ADAPTERS: EngineAdapter[] = ['Claude', 'Codex', 'Gemini']

/** FSM stage → CSS var. Loop markers ("cycle 3") and unknowns fall back to purple. */
export function stageColor(stage: Stage | string): string {
  const map: Record<string, string> = {
    STORMING:  'var(--text-muted)',
    PLANNING:  'var(--text-muted)',
    BUILDING:  'var(--blue)',
    REVIEWING: 'var(--orange)',
    TESTING:   'var(--purple)',
    RETRO:     'var(--runtime)',
    DONE:      'var(--green)',
  }
  return map[stage] ?? 'var(--purple)'
}

export function statusColor(st: EngineStatus): string {
  const map: Record<EngineStatus, string> = {
    running: 'var(--runtime)',
    queued:  'var(--text-muted)',
    done:    'var(--green)',
    failed:  'var(--red)',
  }
  return map[st]
}

export function statusLabel(st: EngineStatus): string {
  const map: Record<EngineStatus, string> = {
    running: 'running',
    queued:  'queued',
    done:    'finished',
    failed:  'failed',
  }
  return map[st]
}

/** The shell command a given adapter runs — used in the detail log preview. */
export function adapterCommand(a: EngineAdapter): string {
  const map: Record<EngineAdapter, string> = {
    Claude: 'claude',
    Codex:  'codex exec',
    Gemini: 'agy',
  }
  return map[a]
}
