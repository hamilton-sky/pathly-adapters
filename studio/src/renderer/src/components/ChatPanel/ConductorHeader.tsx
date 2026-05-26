import { X, Zap, Trash2 } from 'lucide-react'
import { ModelSelector } from './ModelSelector'
import styles from './ConductorHeader.module.css'

interface ConductorHeaderProps {
  hasClaudeTab: boolean
  hasCodexTab: boolean
  onToggleChat: () => void
  onClearChat: () => void
}

export function ConductorHeader({ hasClaudeTab, hasCodexTab, onToggleChat, onClearChat }: ConductorHeaderProps): JSX.Element {

  return (
    <div className={styles.header}>
      <div className={styles.titleRow}>
        <span className={styles.title}>
          <Zap size={13} /> Conductor
        </span>
      </div>

      <div className={styles.pills}>
        <span className={styles.pill}>
          <span className={`${styles.dot} ${hasClaudeTab ? styles.dotActive : ''}`} />
          claude
        </span>
        <span className={styles.pill}>
          <span className={`${styles.dot} ${hasCodexTab ? styles.dotActive : ''}`} />
          codex
        </span>
        <ModelSelector />
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
