import { useRef, useEffect } from 'react'
import { useRunnerStore } from '../../../store/runnerStore'
import type { RunnerStatus } from '../../../store/runnerStore'
import styles from './StageStatusStrip.module.css'

const SESSION_LABELS: Record<string, string> = {
  opened: 'New session',
  continued: 'Continued',
  degraded: 'Degraded',
}

const ADAPTER_COLORS: Record<string, string> = {
  claude: 'var(--accent)',
  codex: 'var(--green)',
  copilot: 'var(--yellow)',
}

function dotClass(status: RunnerStatus): string {
  if (status === 'running') return `${styles.dot} ${styles.dotRunning}`
  if (status === 'finalizing') return `${styles.dot} ${styles.dotFinalizing}`
  if (status === 'paused') return `${styles.dot} ${styles.dotPaused}`
  if (status === 'blocked') return `${styles.dot} ${styles.dotBlocked}`
  if (status === 'error') return `${styles.dot} ${styles.dotError}`
  return `${styles.dot} ${styles.dotIdle}`
}

export function StageStatusStrip(): JSX.Element {
  const status = useRunnerStore((s) => s.status)
  const topic = useRunnerStore((s) => s.topic)
  const stage = useRunnerStore((s) => s.stage)
  const adapter = useRunnerStore((s) => s.adapter)
  const cost = useRunnerStore((s) => s.cost)
  const sessionKind = useRunnerStore((s) => s.sessionKind)
  const errorMessage = useRunnerStore((s) => s.errorMessage)
  const activeRunnerTabId = useRunnerStore((s) => s.activeRunnerTabId)

  const costDisplay = cost === 0 && status === 'idle' ? '—' : `$${cost.toFixed(3)}`
  const adapterColor = adapter ? (ADAPTER_COLORS[adapter] ?? 'var(--text-muted)') : undefined
  const sessionLabel = sessionKind ? SESSION_LABELS[sessionKind] : null
  const chipRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (chipRef.current && adapterColor !== undefined) {
      chipRef.current.style.setProperty('--chip-color', adapterColor)
    }
  }, [adapterColor])

  return (
    <div className={styles.strip}>
      <span className={dotClass(status)} aria-label={`Status: ${status}`} />
      {topic && <span className={styles.topic}>{topic}</span>}
      {topic && <span className={styles.sep} aria-hidden="true">·</span>}
      <span className={styles.stage}>
        {status === 'finalizing' ? `${stage ?? '—'} — finalizing…` : (stage ?? '—')}
      </span>
      {adapter && (
        <span
          ref={chipRef}
          className={styles.adapterChip}
          aria-hidden="true"
        >
          {adapter}
        </span>
      )}
      {!adapter && (
        <span className={styles.adapterChipEmpty} aria-hidden="true">no adapter</span>
      )}
      {status === 'running' && activeRunnerTabId !== null && (
        <button
          type="button"
          className={styles.liveBtn}
          onClick={() => useRunnerStore.getState().jumpToLiveTab()}
          aria-label="Jump to live terminal"
        >
          live ↗
        </button>
      )}
      <span className={styles.cost}>{costDisplay}</span>
      {sessionLabel && (
        <span className={`${styles.session} ${sessionKind === 'degraded' ? styles.sessionDegraded : ''}`}>
          {sessionLabel}
        </span>
      )}
      {errorMessage && (
        <span className={styles.error} role="alert">{errorMessage}</span>
      )}
    </div>
  )
}
