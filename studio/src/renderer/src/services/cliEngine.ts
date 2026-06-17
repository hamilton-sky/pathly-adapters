/**
 * Canonical TypeScript source for CLI spawn argv shapes.
 * All Studio-side spawners import from here — one place to update, one place to debug.
 * Python-side shapes live in src/pathly_data/core/adapters.yaml — keep them in sync.
 */

export type CliAdapter = 'claude' | 'codex' | 'antigravity' | 'copilot'

export interface AdapterMeta {
  id: CliAdapter
  label: string
  hint: string
  /** Set when the adapter has no headless one-shot mode. */
  noHeadless?: string
}

export const ADAPTER_META: AdapterMeta[] = [
  { id: 'claude',      label: 'Claude',  hint: 'Claude Code' },
  { id: 'codex',       label: 'Codex',   hint: 'OpenAI Codex' },
  { id: 'antigravity', label: 'Gemini',  hint: 'Antigravity CLI', noHeadless: 'No one-shot mode configured yet' },
  { id: 'copilot',     label: 'Copilot', hint: 'GitHub Copilot',  noHeadless: 'No headless mode' },
]

export interface SpawnOpts {
  model?: string
  session?: string
  /** Whether to pass the autonomy/auto-accept flag (default true). */
  autonomy?: boolean
}

/**
 * Build argv for a headless one-shot CLI run (notebook AI actions, editor actions, board runs).
 * Mirrors core/adapters.yaml headless + autonomy_flag — keep shapes in sync.
 *
 * Key invariant for Codex: prompt always follows '--' so leading '---' YAML frontmatter
 * is never parsed as a CLI flag.
 */
export function buildHeadlessArgv(adapter: CliAdapter, prompt: string, opts: SpawnOpts = {}): string[] {
  const { model, session, autonomy = true } = opts

  if (adapter === 'claude') {
    const argv = ['claude', '-p', prompt, '--print']
    if (model) argv.push('--model', model)
    if (autonomy) argv.push('--dangerously-skip-permissions')
    if (session) argv.push('--resume', session)
    return argv
  }

  if (adapter === 'codex') {
    const argv = ['codex', 'exec']
    if (autonomy) argv.push('--full-auto')
    if (model) argv.push('--model', model)
    if (session) argv.push('--continue')
    argv.push('--', prompt)
    return argv
  }

  if (adapter === 'antigravity') {
    return buildHeadlessArgv('claude', prompt, opts)
  }

  // copilot: no headless mode — caller should check noHeadless first
  return buildHeadlessArgv('claude', prompt, opts)
}

/** Build argv for an interactive REPL session (no -p, no --print). */
export function buildInteractiveArgv(adapter: CliAdapter, opts: SpawnOpts = {}): string[] {
  const { model, session, autonomy = true } = opts

  if (adapter === 'claude') {
    const argv = ['claude']
    if (model) argv.push('--model', model)
    if (autonomy) argv.push('--dangerously-skip-permissions')
    if (session) argv.push('--resume', session)
    return argv
  }

  if (adapter === 'codex') {
    const argv = ['codex']
    if (model) argv.push('--model', model)
    if (autonomy) argv.push('--full-auto')
    return argv
  }

  return [adapter]
}

/** Human-readable label for an adapter. */
export function adapterLabel(adapter: CliAdapter): string {
  return ADAPTER_META.find((m) => m.id === adapter)?.label ?? adapter
}
