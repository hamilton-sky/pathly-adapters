import { useId } from 'react'
import { Zap } from 'lucide-react'
import type { HqActionCard, HqActionStatus } from '../../../../store/chatStore'
import styles from './ActionCard.module.css'

interface Props {
  card: HqActionCard
  /** False while an earlier card of the same answer is unsettled (cards run in order). */
  runnable: boolean
  onRun: () => void
  onCancel: () => void
}

const RECORD: Record<Exclude<HqActionStatus, 'proposed' | 'running'>, string> = {
  done: '✓ done',
  failed: '✗ failed',
  cancelled: '– cancelled',
  stale: '⟳ not run',
  invalid: '✗ not proposed',
  unavailable: '– not run',
}

/** One proposed action. Proposed: verb + target, its risk in words, Run /
 *  Cancel — Run is never auto-focused and Enter is not bound to it. Every
 *  other status is a one-line record. */
export function ActionCard({ card, runnable, onRun, onCancel }: Props): JSX.Element {
  const waitId = useId()

  if (card.status !== 'proposed' && card.status !== 'running') {
    return (
      <div className={styles.record} data-status={card.status}>
        <span className={styles.recordStatus}>{RECORD[card.status]}</span>
        <span className={styles.recordText}>{card.summary || card.title}</span>
      </div>
    )
  }

  const running = card.status === 'running'
  return (
    <div className={styles.card} role="group" aria-label={`Proposed action: ${card.title}`}>
      <div className={styles.title}>
        <Zap size={12} className={styles.icon} aria-hidden="true" />
        <span>{card.title}</span>
      </div>
      <div className={styles.risk}>
        {card.risk.join(' · ')}
        {card.runs_on === 'studio' ? ' · runs in Studio' : ''}
      </div>
      <div className={styles.actions}>
        <button
          type="button"
          className={styles.run}
          onClick={() => { if (runnable && !running) onRun() }}
          {...(!runnable || running ? { 'aria-disabled': 'true' } : {})}
          {...(!runnable ? { 'aria-describedby': waitId } : {})}
        >
          {running ? 'Running…' : 'Run'}
        </button>
        <button type="button" className={styles.cancel} onClick={onCancel} disabled={running}>
          Cancel
        </button>
        {!runnable && !running && (
          <span id={waitId} className={styles.wait}>Waits for the action above</span>
        )}
      </div>
    </div>
  )
}
