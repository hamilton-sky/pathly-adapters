import { X, Zap, Trash2 } from 'lucide-react'
import type { TerminalKind } from '../../store/chatStore'
import styles from './ConductorHeader.module.css'

interface ConductorHeaderProps {
  hasClaudeTab: boolean
  hasCodexTab: boolean
  targetKind: TerminalKind
  onSetTarget: (kind: TerminalKind) => void
  onToggleChat: () => void
  onClearChat: () => void
}

export function ConductorHeader({ hasClaudeTab, hasCodexTab, targetKind, onSetTarget, onToggleChat, onClearChat }: ConductorHeaderProps): JSX.Element {

  return (
    <div className={styles.header}>
      <div className={styles.titleRow}>
        <span className={styles.title}>
          <Zap size={13} /> Conductor
        </span>
      </div>

      <div className={styles.pills}>
        <button
          className={`${styles.pill} ${targetKind === 'claude' ? styles.pillSelected : ''}`}
          onClick={() => onSetTarget('claude')}
        >
          <span className={`${styles.dot} ${hasClaudeTab ? styles.dotActive : ''}`} />
          claude
        </button>
        <button
          className={`${styles.pill} ${targetKind === 'codex' ? styles.pillSelected : ''}`}
          onClick={() => onSetTarget('codex')}
        >
          <span className={`${styles.dot} ${hasCodexTab ? styles.dotActive : ''}`} />
          codex
        </button>
        <button
          className={`${styles.pill} ${targetKind === 'shell' ? styles.pillSelected : ''}`}
          onClick={() => onSetTarget('shell')}
        >
          <span className={styles.dot} />
          shell
        </button>
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
