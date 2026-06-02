import { useRunnerStore } from '../../../store/runnerStore'
import type { HistoricalRun } from '../../../store/runnerStore'
import type { StageLogEntry } from '../../../store/runnerStore'
import { RunnerLogRow } from './RunnerLogRow'
import styles from './RunnerLogCard.module.css'

function fmtDate(ts: number | null): string {
  if (ts === null) return '—'
  const d = new Date(ts)
  return d.toTimeString().slice(0, 8)
}

interface RunnerLogCardProps {
  historicalRun?: HistoricalRun
  docked?: boolean
}

export function RunnerLogCard({ historicalRun, docked = false }: RunnerLogCardProps = {}): JSX.Element | null {
  const storeStageLog = useRunnerStore((s) => s.stageLog)
  const status = useRunnerStore((s) => s.status)
  const storeCost = useRunnerStore((s) => s.cost)
  const logCardExpanded = useRunnerStore((s) => s.logCardExpanded)
  const storeRunStartedAt = useRunnerStore((s) => s.runStartedAt)
  const activeRunnerTabId = useRunnerStore((s) => s.activeRunnerTabId)

  const stageLog: StageLogEntry[] = historicalRun ? historicalRun.stageLog : storeStageLog
  const cost = historicalRun ? historicalRun.cost : storeCost
  const runStartedAt = historicalRun ? historicalRun.runStartedAt : storeRunStartedAt

  if (!historicalRun && stageLog.length === 0) return null

  const isRunning = !historicalRun && status === 'running'
  const currentEntry = stageLog[stageLog.length - 1]
  const doneCount = stageLog.filter((e) => e.endedAt !== null).length

  const dotClass = isRunning
    ? `${styles.dot} ${styles.dotRunning}`
    : `${styles.dot} ${styles.dotIdle}`

  function handleToggle(): void {
    useRunnerStore.getState().setLogCardExpanded(!logCardExpanded)
  }

  function handleJump(): void {
    useRunnerStore.getState().jumpToLiveTab()
  }

  const expanded = historicalRun ? true : logCardExpanded

  const cardClass = docked ? `${styles.card} ${styles.cardDocked}` : styles.card

  const doneText = `${doneCount} stage${doneCount !== 1 ? 's' : ''} done`
  const stageLabel = currentEntry?.stage ? `${doneText} — ${currentEntry.stage}` : doneText

  return (
    <div className={cardClass} {...(isRunning ? { 'data-running': 'true' } : {})}>
      <div className={styles.headerRow}>
        {!historicalRun ? (
          <button
            type="button"
            className={styles.headerToggle}
            onClick={handleToggle}
            aria-label={logCardExpanded ? 'Collapse stage log' : 'Expand stage log'}
            {...(logCardExpanded ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
          >
            <span className={dotClass} />
            <span className={styles.stageName}>{stageLabel}</span>
            <span className={styles.chevron} data-open={logCardExpanded ? 'true' : 'false'}>▾</span>
          </button>
        ) : (
          <div className={styles.headerStatic}>
            <span className={dotClass} />
            <span className={styles.stageName}>{stageLabel}</span>
          </div>
        )}
        {!historicalRun && activeRunnerTabId !== null && (
          <button type="button" className={styles.jumpBtn} onClick={handleJump}>
            live ↗
          </button>
        )}
      </div>
      <div className={expanded ? `${styles.body} ${styles.bodyOpen}` : styles.body}>
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
