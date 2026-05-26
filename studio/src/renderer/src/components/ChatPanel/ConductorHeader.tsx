import { Brain, X } from 'lucide-react'
import { useUiStore } from '../../store/uiStore'
import { useTerminalStore } from '../../store/terminalStore'
import { useTheme } from '../../useTheme'
import styles from './ConductorHeader.module.css'

export function ConductorHeader(): JSX.Element {
  const toggleChat = useUiStore((s) => s.toggleChat)
  const tabs = useTerminalStore((s) => s.tabs)
  const t = useTheme()

  const hasClaudeTab = tabs.some((tab) => tab.kind === 'claude')
  const hasCodexTab = tabs.some((tab) => tab.kind === 'codex')

  return (
    <div
      className={styles.header}
      style={{ borderBottom: t.border, background: t.bgMantle }}
    >
      <div className={styles.titleRow}>
        <Brain size={15} style={{ color: t.accent }} />
        <span className={styles.title} style={{ color: t.textPrimary, fontFamily: t.fontFamilyBase }}>
          Conductor
        </span>
      </div>

      <div className={styles.pills}>
        <span
          className={styles.pill}
          style={{ background: t.bgSurface0, color: t.textSecondary, fontFamily: t.fontFamilyMono }}
        >
          <span
            className={styles.dot}
            style={{ background: hasClaudeTab ? t.green : t.textMuted }}
          />
          claude
        </span>
        <span
          className={styles.pill}
          style={{ background: t.bgSurface0, color: t.textSecondary, fontFamily: t.fontFamilyMono }}
        >
          <span
            className={styles.dot}
            style={{ background: hasCodexTab ? t.green : t.textMuted }}
          />
          codex
        </span>
      </div>

      <button
        className={styles.closeBtn}
        onClick={toggleChat}
        aria-label="Close chat panel"
        style={{ color: t.textMuted }}
      >
        <X size={14} />
      </button>
    </div>
  )
}
