import type { StageLogEntry } from '../../../store/runnerStore'
import { formatClock } from '../../../utils/timestamp'
import styles from './RunnerLogCard.module.css'

interface Props {
  entry: StageLogEntry
}

function fmtDuration(startedAt: number, endedAt: number | null): string {
  if (endedAt === null) return '…'
  const secs = Math.round((endedAt - startedAt) / 1000)
  return `${secs}s`
}

export function RunnerLogRow({ entry }: Props): JSX.Element {
  const isHeadless = entry.mode === 'headless'
  const isRunning = entry.endedAt === null
  const statusClass = isRunning
    ? `${styles.dot} ${styles.dotRunning}`
    : entry.exitCode === 0 || entry.exitCode === null
    ? `${styles.dot} ${styles.dotDone}`
    : `${styles.dot} ${styles.dotError}`

  return (
    <tr className={styles.row}>
      <td className={styles.cellStage}>{entry.stage}</td>
      <td className={isHeadless ? styles.cellAdapterHeadless : styles.cellAdapter}>
        {isHeadless ? '— headless' : (entry.adapter ?? '—')}
      </td>
      <td className={styles.cellTime}>{formatClock(entry.startedAt)}</td>
      <td className={styles.cellDuration}>{fmtDuration(entry.startedAt, entry.endedAt)}</td>
      <td className={styles.cellStatus}>
        <span className={statusClass} aria-label={isRunning ? 'running' : entry.exitCode === 0 ? 'done' : 'error'} />
      </td>
    </tr>
  )
}
