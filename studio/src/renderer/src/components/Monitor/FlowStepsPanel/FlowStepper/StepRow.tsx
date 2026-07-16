import { Check, CircleDot } from 'lucide-react'
import type { FlowStep } from '../flowSteps'
import styles from './FlowStepper.module.css'

interface StepRowProps {
  step: FlowStep
  isLast: boolean
  onClick: (state: string) => void
}

/**
 * One vertical step: a decorative rail (status dot + connector) beside a clickable label that
 * opens the Configure-phase modal for that stage. The dot/connector are aria-hidden; the button
 * carries the accessible label so the stepper reads as one actionable item per phase.
 */
export function StepRow({ step, isLast, onClick }: StepRowProps): JSX.Element {
  const { state, role, status, retryCount } = step
  const label =
    status === 'active-retry' ? `${state} — retried ${retryCount}×` : `${state} — ${status}`

  return (
    <li className={styles.row}>
      <div className={styles.rail} aria-hidden="true">
        <span className={styles.dot} data-status={status}>
          {status === 'completed' && <Check size={12} />}
          {(status === 'active' || status === 'active-retry') && <CircleDot size={12} />}
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
          {role && <span className={styles.role}>{role}</span>}
          {status === 'active-retry' && retryCount > 0 && (
            <span className={styles.retry}>↩{retryCount}</span>
          )}
        </span>
      </button>
    </li>
  )
}
