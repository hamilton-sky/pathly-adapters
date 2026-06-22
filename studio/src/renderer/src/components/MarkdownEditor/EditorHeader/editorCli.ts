// CLI engine selection for the notebook's one-shot agent actions (AI Split, AI Analyze).
// Argv shapes are owned by cliEngine.ts — import from there, never define them inline.

import { buildHeadlessArgv, ADAPTER_META } from '../../../services/cliEngine'
export type { CliAdapter as EditorCli } from '../../../services/cliEngine'
import type { CliAdapter } from '../../../services/cliEngine'

export interface CliOption {
  id: CliAdapter
  label: string
  hint: string
  unavailable?: string
}

export const EDITOR_CLIS: CliOption[] = ADAPTER_META.map((m) => ({
  id: m.id,
  label: m.label,
  hint: m.hint,
  ...(m.noHeadless ? { unavailable: m.noHeadless } : {}),
}))

// Engine choice is persisted per action so AI Split and AI Analyze can use
// different engines independently.
export const CLI_KEY_SPLIT   = 'pathly.notebook.cli.split'
export const CLI_KEY_ANALYZE = 'pathly.notebook.cli.analyze'
export const CLI_KEY_EVAL    = 'pathly.comms.cli.eval'
export const CLI_KEY_GOAL    = 'pathly.comms.cli.goal'

export function loadEditorCli(key: string): CliAdapter {
  try {
    const v = localStorage.getItem(key)
    if (v && EDITOR_CLIS.some((c) => c.id === v && !c.unavailable)) return v as CliAdapter
  } catch { /* ignore */ }
  return 'claude'
}

export function saveEditorCli(key: string, cli: CliAdapter): void {
  try { localStorage.setItem(key, cli) } catch { /* ignore */ }
}

/** Resolve the spawn argv for the selected engine; falls back to Claude if unavailable. */
export function buildCliArgv(cli: CliAdapter, prompt: string): string[] {
  return buildHeadlessArgv(cli, prompt)
}

/** Human-friendly engine name for toasts/labels. */
export function cliLabel(cli: CliAdapter): string {
  return EDITOR_CLIS.find((c) => c.id === cli)?.label ?? cli
}
