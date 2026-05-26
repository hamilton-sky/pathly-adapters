import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { useTheme } from '../../useTheme'
import styles from './OutputSnippet.module.css'

interface OutputSnippetProps {
  target: 'claude-code' | 'codex'
  status: 'running' | 'done' | 'error'
  lines: string[]
}

export function OutputSnippet({ target, status, lines }: OutputSnippetProps): JSX.Element {
  const t = useTheme()
  const [expanded, setExpanded] = useState(false)

  const targetColor = target === 'claude-code' ? '#38BDF8' : '#F59E0B'
  const targetLabel = target === 'claude-code' ? 'claude' : 'codex'

  // Collapsed: show only the last line as a preview
  const previewLine = lines[lines.length - 1] ?? ''
  // Expanded: show all lines (or at most 40 to stay performant)
  const visibleLines = lines.slice(-40)

  return (
    <div
      className={styles.block}
      style={{ background: t.bgMantle, color: t.textSecondary, border: `1px solid ${t.bgSurface0}` }}
    >
      {/* ── Header row — always visible ── */}
      <div className={styles.header}>
        <span className={styles.targetLabel} style={{ color: targetColor }}>
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

        <span className={styles.statusText}>
          {status === 'running' ? 'running…' : status === 'done' ? '✓ done' : '✕ error'}
        </span>

        {/* Line count badge */}
        {lines.length > 0 && (
          <span className={styles.lineCount}>{lines.length} line{lines.length !== 1 ? 's' : ''}</span>
        )}

        {/* Spacer */}
        <span style={{ flex: 1 }} />

        {/* Toggle button */}
        <button
          className={styles.toggleBtn}
          onClick={() => setExpanded((v) => !v)}
          aria-label={expanded ? 'Collapse output' : 'Show output'}
          title={expanded ? 'Collapse' : 'Show more'}
        >
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          <span>{expanded ? 'collapse' : 'show more'}</span>
        </button>
      </div>

      {/* ── Collapsed preview — single line ── */}
      {!expanded && (
        <div className={styles.preview}>
          {lines.length === 0
            ? <span className={styles.empty}>waiting for output…</span>
            : <span className={styles.previewLine}>{previewLine}</span>
          }
        </div>
      )}

      {/* ── Expanded full output ── */}
      {expanded && (
        <ul className={styles.lines}>
          {visibleLines.length === 0
            ? <li className={styles.empty}>waiting for output…</li>
            : visibleLines.map((line, i) => (
                <li key={i} className={styles.line}>{line}</li>
              ))
          }
        </ul>
      )}
    </div>
  )
}
