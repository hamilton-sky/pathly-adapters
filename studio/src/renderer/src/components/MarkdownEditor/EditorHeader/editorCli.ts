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
const CLI_KEY_EVAL    = 'pathly.comms.cli.eval'
export const CLI_KEY_GOAL    = 'pathly.comms.cli.goal'
export const CLI_KEY_TASK    = 'pathly.comms.cli.task'

export const CLI_KEY_COMMENT = 'pathly.editor.cli.comment'

// Preset name is persisted per action independently of the prompt text override.
export const PRESET_KEY_SPLIT    = 'pathly.notebook.preset.split'
export const PRESET_KEY_ANALYZE  = 'pathly.notebook.preset.analyze'
export const PRESET_KEY_COMMENT  = 'pathly.editor.preset.comment'

// Comment-defaults config: persisted extra-instructions + prompt-framing override
// (string load/save reuses loadPreset/savePreset).
export const COMMENT_EXTRA_KEY  = 'pathly.editor.comment.extra'
export const COMMENT_PROMPT_KEY = 'pathly.editor.comment.prompt'

export function loadPreset(key: string, fallback = ''): string {
  try { return localStorage.getItem(key) ?? fallback } catch { return fallback }
}

export function savePreset(key: string, name: string): void {
  try { localStorage.setItem(key, name) } catch { /* ignore */ }
}

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

/** Resolve the spawn argv for the selected engine; falls back to Claude if unavailable.
 *  Uses claude's single-envelope `--output-format json` (NOT stream-json): these actions WRITE a
 *  sidecar file, and stream-json's headless permission loop blocked the write — claude asked for
 *  approval instead of writing, so no artifact AND no cost was recorded. json mode honors
 *  `--dangerously-skip-permissions` (like the supervisor runs that write files fine) and the gate
 *  captures cost/tokens reliably from the final result envelope. Trade-off: the terminal buffers
 *  instead of streaming token-by-token; the result still lands in the gallery + progress toasts.
 *  Codex is unaffected (it uses `--json` unconditionally). */
export function buildCliArgv(cli: CliAdapter, prompt: string, model = ''): string[] {
  return buildHeadlessArgv(cli, prompt, { jsonOutput: true, ...(model ? { model } : {}) })
}

/** Human-friendly engine name for toasts/labels. */
export function cliLabel(cli: CliAdapter): string {
  return EDITOR_CLIS.find((c) => c.id === cli)?.label ?? cli
}
