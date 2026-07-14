/**
 * Canonical TypeScript source for CLI spawn argv shapes.
 * All Studio-side spawners import from here — one place to update, one place to debug.
 * Python-side shapes live in src/pathly_data/core/adapters.yaml — keep them in sync.
 */

import { ADAPTERS, type CliAdapter } from '../lib/adapters.gen'

export type { CliAdapter }

export interface AdapterMeta {
  id: CliAdapter
  label: string
  hint: string
  /** Set when the adapter has no headless one-shot mode — the greyed reason. */
  noHeadless?: string
}

// DERIVED from the ONE source: core/adapters.yaml -> adapters.gen.ts. A non-headless
// engine is listed but greyed with this reason. Add or enable an engine by editing
// adapters.yaml + `python scripts/gen_adapters_ts.py` — never by hand-editing a list here.
export const ADAPTER_META: AdapterMeta[] = Object.entries(ADAPTERS).map(([id, m]) => ({
  id: id as CliAdapter,
  label: m.label,
  hint: m.hint,
  noHeadless: m.headless ? undefined : 'No headless one-shot mode',
}))

export interface SpawnOpts {
  model?: string
  session?: string
  /** Whether to pass the autonomy/auto-accept flag (default true). */
  autonomy?: boolean
  /** Stream structured events (claude `--output-format stream-json`) instead of plain text.
   *  The main-process spawn gate (terminal.ts) renders these events back into clean prose +
   *  live "⚙ Tool" lines, so streaming UX is preserved while it captures cost / tokens /
   *  tool-call count from the final `result` event. Claude only — codex ignores it. */
  streamJson?: boolean
}

/**
 * Strip a leading YAML-frontmatter / '---' block so a prompt can never start with
 * '--'. For claude the prompt is a bare positional after -p, and an argument
 * starting with '--' is parsed as an unknown option ("error: unknown option '---...'").
 * Mirrors the Python _dash_safe_prompt in src/pathly_orchestrator/adapters.py.
 */
export function dashSafePrompt(prompt: string): string {
  let s = prompt.replace(/^\s+/, '')
  const m = s.match(/^---[ \t]*\n[\s\S]*?\n---[ \t]*\n/)
  if (m) s = s.slice(m[0].length).replace(/^\s+/, '')
  s = s.replace(/^(?:-{3,}[ \t]*\n\s*)+/, '')
  return s
}

/**
 * Build argv for a headless one-shot CLI run (notebook AI actions, editor actions, board runs).
 * Mirrors core/adapters.yaml headless + autonomy_flag — keep shapes in sync.
 *
 * Key invariant for Codex: prompt always follows '--' so leading '---' YAML frontmatter
 * is never parsed as a CLI flag.
 */
export function buildHeadlessArgv(adapter: CliAdapter, promptRaw: string, opts: SpawnOpts = {}): string[] {
  const { model, session, autonomy = true, streamJson } = opts
  const prompt = dashSafePrompt(promptRaw)

  if (adapter === 'claude') {
    const argv = ['claude', '-p', prompt, '--print']
    // stream-json events → the spawn gate renders them to clean text + tool lines and reads
    // cost/tokens/tool-count from the final result event. --verbose is required for the full
    // event stream in -p mode.
    if (streamJson) argv.push('--output-format', 'stream-json', '--verbose')
    if (model) argv.push('--model', model)
    if (autonomy) argv.push('--dangerously-skip-permissions')
    if (session) argv.push('--resume', session)
    return argv
  }

  if (adapter === 'codex') {
    // --skip-git-repo-check: codex exec refuses to run ("Not inside a trusted directory")
    // when the cwd isn't a trusted git repo — e.g. an arbitrary file's folder for Analyze/Split.
    // --json: emit JSONL events (incl. token usage) so the spawn gate's parseCodexResult can
    // capture tokens → the server estimates cost (db/pricing.py). Mirrors core/adapters.yaml's
    // codex template; without it codex prints plain text, no usage is seen, and the one-shot
    // records 0 tokens / $0 (the diagrammer/splitter gap). codex reports NO dollar cost either way.
    const argv = ['codex', 'exec', '--skip-git-repo-check', '--json']
    if (autonomy) argv.push('--sandbox', 'workspace-write')
    if (model) argv.push('--model', model)
    if (session) argv.push('--continue')
    argv.push('--', prompt)
    return argv
  }

  if (adapter === 'antigravity') {
    // agy (Antigravity / Gemini CLI) headless one-shot — mirrors core/adapters.yaml.
    // No JSON/stream mode (prints plain text); auto-approve = --dangerously-skip-permissions.
    const argv = ['agy', '-p', prompt]
    if (model) argv.push('--model', model)
    if (autonomy) argv.push('--dangerously-skip-permissions')
    return argv
  }

  // copilot has no headless one-shot mode. Fail loud instead of silently building the claude
  // argv (the old behavior mis-attributed the run to the wrong engine). The UI already filters
  // it out via ADAPTER_META.noHeadless; this is the honest backstop.
  const meta = ADAPTER_META.find((m) => m.id === adapter)
  throw new Error(
    `Adapter '${adapter}' has no headless mode` +
      (meta?.noHeadless ? ` (${meta.noHeadless})` : '') +
      '. Use claude, codex, or antigravity for headless runs.'
  )
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
    if (autonomy) argv.push('--sandbox', 'workspace-write')
    return argv
  }

  return [adapter]
}

/** Human-readable label for an adapter. */
export function adapterLabel(adapter: CliAdapter): string {
  return ADAPTER_META.find((m) => m.id === adapter)?.label ?? adapter
}
