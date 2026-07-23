import { Check, CircleDot, Settings2 } from 'lucide-react'
import type { FlowStep } from '../flowSteps'
import styles from './FlowStepper.module.css'

interface StepRowProps {
  step: FlowStep
  index: number
  isLast: boolean
  onClick: (state: string) => void
}

/**
 * One vertical step: a decorative rail (status dot + connector) beside a clickable label that
 * opens the Configure-phase modal for that stage. Completed steps carry a check on a green
 * gradient, the active step a pulsing accent dot inside a tinted row card, pending steps their
 * 1-based stage number on a dashed ring. The dot/connector are aria-hidden; the button carries
 * the accessible label plus a hover gear as the configure affordance.
 */
export function StepRow({ step, index, isLast, onClick }: StepRowProps): JSX.Element {
  const { state, role, status, retryCount } = step
  const label =
    status === 'active-retry' ? `${state} — retried ${retryCount}×` : `${state} — ${status}`

  return (
    <li className={styles.row} data-status={status}>
      <div className={styles.rail} aria-hidden="true">
        <span className={styles.dot} data-status={status}>
          {status === 'completed' && <Check size={12} strokeWidth={3} />}
          {(status === 'active' || status === 'active-retry') && <CircleDot size={13} />}
          {status === 'pending' && <span className={styles.num}>{index + 1}</span>}
        </span>
        {!isLast && (
          <span
            className={styles.connector}
            {...(status === 'completed' ? { 'data-done': '' } : {})}
          />
        )}
      </div>
      <button
        type="button"
        className={styles.stepBtn}
        onClick={() => onClick(state)}
        aria-label={`Configure ${label}`}
        title="Configure this stage"
      >
        <span className={styles.state} data-status={status}>
          {state}
        </span>
        <span className={styles.meta}>
          {role && (
            <span className={styles.role} data-status={status}>
              {role}
            </span>
          )}
          {status === 'active-retry' && retryCount > 0 && (
            <span className={styles.retry}>↩{retryCount}</span>
          )}
        </span>
        <Settings2 size={12} className={styles.gear} aria-hidden="true" />
      </button>
    </li>
  )
}
