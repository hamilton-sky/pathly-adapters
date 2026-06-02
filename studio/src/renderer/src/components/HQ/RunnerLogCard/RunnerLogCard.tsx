import { useRunnerStore } from '../../../store/runnerStore'
import { RunnerLogRow } from './RunnerLogRow'
import styles from './RunnerLogCard.module.css'

function fmtDate(ts: number | null): string {
  if (ts === null) return '—'
  const d = new Date(ts)
  return d.toTimeString().slice(0, 8)
}

export function RunnerLogCard(): JSX.Element | null {
  const stageLog = useRunnerStore((s) => s.stageLog)
  const status = useRunnerStore((s) => s.status)
  const cost = useRunnerStore((s) => s.cost)
  const logCardExpanded = useRunnerStore((s) => s.logCardExpanded)
  const runStartedAt = useRunnerStore((s) => s.runStartedAt)
  const activeRunnerTabId = useRunnerStore((s) => s.activeRunnerTabId)

  if (stageLog.length === 0) return null

  const isRunning = status === 'running'
  const currentEntry = stageLog[stageLog.length - 1]
  const doneCount = stageLog.filter((e) => e.endedAt !== null).length

  const dotClass = isRunning
    ? `${styles.dot} ${styles.dotRunning}`
    : `${styles.dot} ${styles.dotIdle}`

  const cardClass = isRunning
    ? `${styles.card} ${styles.cardRunning}`
    : styles.card

  function handleToggle(): void {
    useRunnerStore.getState().setLogCardExpanded(!logCardExpanded)
  }

  function handleJump(): void {
    useRunnerStore.getState().jumpToLiveTab()
  }

  return (
    <div className={cardClass} data-running={isRunning}>
      <div className={styles.headerRow}>
        <span className={dotClass} aria-label={`Runner status: ${status}`} />
        <span className={styles.stageName}>
          {doneCount} stage{doneCount !== 1 ? 's' : ''} done — {currentEntry.stage}
        </span>
        <button
          type="button"
          className={styles.toggleBtn}
          onClick={handleToggle}
          aria-label={logCardExpanded ? 'Collapse stage log' : 'Expand stage log'}
          {...(logCardExpanded ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        >
          <span className={styles.chevron} data-open={logCardExpanded ? 'true' : 'false'}>▾</span>
        </button>
        {activeRunnerTabId !== null && (
          <button type="button" className={styles.jumpBtn} onClick={handleJump}>
            live ↗
          </button>
        )}
      </div>
      <div className={logCardExpanded ? `${styles.body} ${styles.bodyOpen}` : styles.body}>
        <table className={styles.table}>
          <colgroup>
            <col className={styles.colStage} />
            <col className={styles.colAdapter} />
            <col className={styles.colTime} />
            <col className={styles.colDuration} />
            <col className={styles.colStatus} />
          </colgroup>
          <thead>
            <tr>
              <th className={styles.th}>Stage</th>
              <th className={styles.th}>Adapter</th>
              <th className={styles.th}>Time</th>
              <th className={styles.th}>Dur.</th>
              <th className={styles.th} aria-label="Status" />
            </tr>
          </thead>
          <tbody>
            {stageLog.map((entry, i) => (
              <RunnerLogRow key={`${entry.stage}-${i}`} entry={entry} />
            ))}
          </tbody>
        </table>
        <div className={styles.footer}>
          Started {fmtDate(runStartedAt)} · {stageLog.length} total · ${cost.toFixed(3)}
        </div>
      </div>
    </div>
  )
}
