import { X, Zap, Trash2 } from 'lucide-react'
import type { TerminalKind } from '../../store/chatStore'
import { ClaudeIcon, CodexIcon, ShellIcon } from '../Terminal/BrandIcons'
import styles from './ConductorHeader.module.css'

interface ConductorHeaderProps {
  hasClaudeTab: boolean
  hasCodexTab: boolean
  hasShellTab: boolean
  targetKind: TerminalKind
  onSetTarget: (kind: TerminalKind) => void
  onToggleChat: () => void
  onClearChat: () => void
}

export function ConductorHeader({ hasClaudeTab, hasCodexTab, hasShellTab, targetKind, onSetTarget, onToggleChat, onClearChat }: ConductorHeaderProps): JSX.Element {
  const targetPills: Array<{
    kind: TerminalKind
    label: string
    icon: JSX.Element
    active: boolean
  }> = [
    { kind: 'claude', label: 'claude', icon: <ClaudeIcon size={14} />, active: hasClaudeTab },
    { kind: 'codex', label: 'codex', icon: <CodexIcon size={14} />, active: hasCodexTab },
    { kind: 'shell', label: 'shell', icon: <ShellIcon size={14} />, active: hasShellTab },
  ]

  return (
    <div className={styles.header}>
      <div className={styles.titleRow}>
        <span className={styles.title}>
          <Zap size={13} /> Conductor
        </span>
      </div>

      <div className={styles.pills}>
        {targetPills.map((pill) => (
          <button
            key={pill.kind}
            className={`${styles.pill} ${targetKind === pill.kind ? styles.pillSelected : ''}`}
            onClick={() => onSetTarget(pill.kind)}
          >
            <span className={styles.pillIcon}>{pill.icon}</span>
            <span className={`${styles.dot} ${pill.active ? styles.dotActive : ''}`} />
            {pill.label}
          </button>
        ))}
      </div>

      <button
        className={styles.closeBtn}
        onClick={onClearChat}
        aria-label="Clear chat session"
        title="Clear chat"
      >
        <Trash2 size={13} />
      </button>

      <button
        className={styles.closeBtn}
        onClick={onToggleChat}
        aria-label="Close chat panel"
      >
        <X size={14} />
      </button>
    </div>
  )
}
