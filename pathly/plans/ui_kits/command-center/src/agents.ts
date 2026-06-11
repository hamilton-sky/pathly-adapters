import type { AgentId, Stage, MessageType, BoardScope } from './types';

// ── Agent identity ──────────────────────────────────────────────────
// No emoji in product UI — each agent is a stage-coloured lucide glyph.

export interface AgentMeta {
  label: string;
  color: string;          // CSS token; undefined for the human "you" chip
  icon: string | null;    // lucide name; null → gradient "YOU" chip
}

export const AGENTS: Record<AgentId, AgentMeta> = {
  you:       { label: 'you',       color: 'var(--brand-gradient)', icon: null },
  builder:   { label: 'builder',   color: 'var(--state-building)',  icon: 'square-terminal' },
  reviewer:  { label: 'reviewer',  color: 'var(--state-reviewing)', icon: 'search' },
  architect: { label: 'architect', color: 'var(--state-planning)',  icon: 'git-branch' },
  tester:    { label: 'tester',    color: 'var(--state-testing)',   icon: 'circle-check' },
  retro:     { label: 'retro',     color: 'var(--state-retro)',     icon: 'history' },
};

export const STAGE_COLOR: Record<Stage, string> = {
  PLANNING:  'var(--state-planning)',
  BUILDING:  'var(--state-building)',
  REVIEWING: 'var(--state-reviewing)',
  TESTING:   'var(--state-testing)',
  RETRO:     'var(--state-retro)',
  DONE:      'var(--state-done)',
};

// Message types offered in the compose type-picker, in order.
export const COMPOSE_TYPES: MessageType[] = [
  'nudge', 'decision', 'question', 'task', 'discovery', 'warning',
];

// Board-scope presentation metadata.
export const SCOPES: Record<BoardScope, { icon: string; label: string; title: string }> = {
  feature: { icon: 'git-branch', label: 'Feature board', title: 'FEATURE BOARD' },
  project: { icon: 'folder',     label: 'Project',       title: 'PROJECT BOARD' },
  global:  { icon: 'globe',      label: 'Global',        title: 'GLOBAL BOARD' },
};
