// CLI engine selection for the notebook's one-shot agent actions (AI Split, AI Analyze).
// Each action spawns a headless CLI that follows the prompt and writes a single file
// (.draft / .analysis), then exits. Only the spawn argv differs per engine — the
// spawn + file-poll mechanism in useNotebookAgentActions is engine-agnostic.

export type NotebookCli = 'claude' | 'codex' | 'antigravity' | 'copilot'

export interface CliOption {
  id: NotebookCli
  label: string
  /** Short descriptor shown on the menu row. */
  hint: string
  /** When set, the engine has no one-shot mode — the row is shown but disabled. */
  unavailable?: string
  /** Build the headless spawn argv for a one-shot run of `prompt`. */
  buildArgv?: (prompt: string) => string[]
}

// argv shapes mirror src/pathly_data/core/adapters.yaml `headless` + `autonomy_flag`.
// Only argv[0] values in terminal.ts ALLOWED_SHELLS can be spawned (claude, codex, agy).
export const NOTEBOOK_CLIS: CliOption[] = [
  {
    id: 'claude',
    label: 'Claude',
    hint: 'Claude Code',
    buildArgv: (p) => ['claude', '-p', p, '--print', '--dangerously-skip-permissions'],
  },
  {
    id: 'codex',
    label: 'Codex',
    hint: 'OpenAI Codex',
    buildArgv: (p) => ['codex', 'exec', p, '--full-auto'],
  },
  {
    id: 'antigravity',
    label: 'Gemini',
    hint: 'Antigravity CLI',
    unavailable: 'No one-shot mode configured yet',
  },
  {
    id: 'copilot',
    label: 'Copilot',
    hint: 'GitHub Copilot',
    unavailable: 'No headless mode',
  },
]

// Engine choice is persisted per action so AI Split and AI Analyze can use
// different engines independently.
export const CLI_KEY_SPLIT = 'pathly.notebook.cli.split'
export const CLI_KEY_ANALYZE = 'pathly.notebook.cli.analyze'

export function loadNotebookCli(key: string): NotebookCli {
  try {
    const v = localStorage.getItem(key)
    if (v && NOTEBOOK_CLIS.some((c) => c.id === v && !c.unavailable)) return v as NotebookCli
  } catch { /* ignore */ }
  return 'claude'
}

export function saveNotebookCli(key: string, cli: NotebookCli): void {
  try { localStorage.setItem(key, cli) } catch { /* ignore */ }
}

/** Resolve the spawn argv for the selected engine; falls back to Claude if unavailable. */
export function buildCliArgv(cli: NotebookCli, prompt: string): string[] {
  const opt = NOTEBOOK_CLIS.find((c) => c.id === cli)
  if (opt?.buildArgv) return opt.buildArgv(prompt)
  return ['claude', '-p', prompt, '--print', '--dangerously-skip-permissions']
}

/** Human-friendly engine name for toasts/labels. */
export function cliLabel(cli: NotebookCli): string {
  return NOTEBOOK_CLIS.find((c) => c.id === cli)?.label ?? cli
}
