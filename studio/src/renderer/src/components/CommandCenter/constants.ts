import type { AgentId, Stage, MessageType, BoardScope } from './types'

// Agent identity — no emoji in product UI; each agent is a stage-coloured lucide glyph.
// color strings are CSS tokens only — not injected inline; used via data-agent CSS selectors.

export interface AgentMeta {
  label: string
  color: string  // CSS token reference — used by data-agent CSS rule, not inline style
  icon: string | null  // lucide name; null → gradient "YOU" chip
}

const AGENTS: Record<AgentId, AgentMeta> = {
  you:       { label: 'you',       color: 'var(--brand-gradient)',  icon: 'user' },
  builder:   { label: 'builder',   color: 'var(--state-building)',  icon: 'square-terminal' },
  reviewer:  { label: 'reviewer',  color: 'var(--state-reviewing)', icon: 'search' },
  architect: { label: 'architect', color: 'var(--state-planning)',  icon: 'git-branch' },
  tester:    { label: 'tester',    color: 'var(--state-testing)',   icon: 'circle-check' },
  retro:     { label: 'retro',     color: 'var(--state-retro)',     icon: 'history' },
}

// Identity for ANY agent role — not just the six known ones. Board runs can use
// any agent (explorer, evaluator, …) or post lifecycle messages as 'system', so
// unknown roles get a generic glyph and their real name as the label (rather than
// being collapsed to 'builder').
export function agentMeta(from: string): AgentMeta {
  const known = (AGENTS as Record<string, AgentMeta>)[from]
  if (known) return known
  return { label: from, color: 'var(--text-muted)', icon: 'square-terminal' }
}

const STAGE_COLOR: Record<Stage, string> = {
  PLANNING:  'var(--state-planning)',
  BUILDING:  'var(--state-building)',
  REVIEWING: 'var(--state-reviewing)',
  TESTING:   'var(--state-testing)',
  RETRO:     'var(--state-retro)',
  DONE:      'var(--state-done)',
}

// Message types offered in the compose type-picker, in display order.
export const COMPOSE_TYPES: MessageType[] = [
  'nudge', 'decision', 'question', 'task', 'discovery', 'warning',
]

// Board-scope presentation metadata.
export const SCOPES: Record<BoardScope, { icon: string; label: string; title: string }> = {
  feature: { icon: 'git-branch', label: 'Feature board', title: 'FEATURE BOARD' },
  project: { icon: 'folder',     label: 'Project',       title: 'PROJECT BOARD' },
  global:  { icon: 'globe',      label: 'Global',        title: 'GLOBAL BOARD' },
}
