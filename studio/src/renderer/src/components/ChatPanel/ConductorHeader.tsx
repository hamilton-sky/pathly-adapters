import { X, Zap } from 'lucide-react'
import styles from './ConductorHeader.module.css'

interface ConductorHeaderProps {
  hasClaudeTab: boolean
  hasCodexTab: boolean
  onToggleChat: () => void
}

export function ConductorHeader({ hasClaudeTab, hasCodexTab, onToggleChat }: ConductorHeaderProps): JSX.Element {
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
      </div>

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
