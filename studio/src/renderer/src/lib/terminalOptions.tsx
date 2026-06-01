import { AntigravityIcon, ClaudeIcon, CodexIcon, ShellIcon } from '../components/Terminal/BrandIcons'
import type { TerminalKind } from '../store/chatStore'

export interface TerminalOption {
  kind: TerminalKind
  command: string | undefined  // CLI arg to spawn; undefined = plain shell
  label: string
  icon: (size: number) => JSX.Element
}

export const TERMINAL_OPTIONS: TerminalOption[] = [
  { kind: 'shell',       command: undefined, label: 'Shell',       icon: (s) => <ShellIcon       size={s} /> },
  { kind: 'claude',      command: 'claude',  label: 'Claude Code', icon: (s) => <ClaudeIcon      size={s} /> },
  { kind: 'codex',       command: 'codex',   label: 'Codex',       icon: (s) => <CodexIcon       size={s} /> },
  { kind: 'antigravity', command: 'agy',     label: 'Antigravity', icon: (s) => <AntigravityIcon size={s} /> },
]
