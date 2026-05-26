import { useTheme } from '../../useTheme'
import styles from './OutputSnippet.module.css'

interface OutputSnippetProps {
  target: 'claude-code' | 'codex'
  status: 'running' | 'done' | 'error'
  lines: string[]
}

export function OutputSnippet({ target, status, lines }: OutputSnippetProps): JSX.Element {
  const t = useTheme()

  const targetColor = target === 'claude-code' ? '#38BDF8' : '#F59E0B'
  const targetLabel = target === 'claude-code' ? 'claude' : 'codex'

  return (
    <div
      className={styles.block}
      style={{ background: t.bgMantle, color: t.textSecondary }}
    >
      <div className={styles.header}>
        <span
          className={styles.targetLabel}
          style={{ color: targetColor }}
        >
          {targetLabel}
        </span>
        <div
          className={`${styles.statusDot} ${
            status === 'running'
              ? styles.statusDotRunning
              : status === 'done'
              ? styles.statusDotDone
              : styles.statusDotError
          }`}
        />
        <span className={styles.statusIcon}>
          {status === 'done' ? '✓' : status === 'error' ? '✕' : ''}
        </span>
      </div>

      {lines.length === 0 ? (
        <span className={styles.empty}>waiting for output…</span>
      ) : (
        <ul className={styles.lines}>
          {lines.map((line, i) => (
            <li key={i} className={styles.line}>
              {line}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
