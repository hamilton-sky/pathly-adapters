import { CircleDot } from 'lucide-react'
import type { FlowStep } from '../../../Monitor/FlowStepsPanel/flowSteps'
import styles from './FlowGateStepper.module.css'

interface GateStepRowProps {
  step: FlowStep
  isLast: boolean
  active: boolean
  onSelect: (state: string) => void
}

// ~30-line mirror of Monitor/FlowStepsPanel/FlowStepper/StepRow — rail dot + connector +
// clickable label — but highlighted by the gate's SELECTED stage, not the FSM's live
// status, and titled as a preview affordance. Deliberately not reused directly: StepRow is
// store-coupled to the running flow (DESIGN.md ss1a).
function GateStepRow({ step, isLast, active, onSelect }: GateStepRowProps): JSX.Element {
  const { state, role } = step
  return (
    <li className={styles.row}>
      <div className={styles.rail} aria-hidden="true">
        <span className={styles.dot} {...(active ? { 'data-active': '' } : {})}>
          {active && <CircleDot size={12} />}
        </span>
        {!isLast && <span className={styles.connector} />}
      </div>
      <button
        type="button"
        className={styles.stepBtn}
        {...(active ? { 'data-active': '' } : {})}
        onClick={() => onSelect(state)}
        aria-label={`Preview ${state}${role ? ` — ${role}` : ''}`}
        title="Preview this stage's prompt"
      >
        <span className={styles.state}>{state}</span>
        {role && <span className={styles.role}>{role}</span>}
      </button>
    </li>
  )
}

interface FlowGateStepperProps {
  steps: FlowStep[]
  selectedState: string
  onSelect: (state: string) => void
  /** Layout: 'vertical' (stacked rail) or 'horizontal' (left→right rail). */
  orientation: 'vertical' | 'horizontal'
}

/** Presentational stepper for the gate — selection-driven, not FSM-status-driven. Renders
 *  vertically or horizontally; the CSS keys the two layouts off `data-orientation`. */
export function FlowGateStepper({ steps, selectedState, onSelect, orientation }: FlowGateStepperProps): JSX.Element {
  if (steps.length === 0) {
    return <p className={styles.empty}>No stages to preview.</p>
  }
  return (
    <ol className={styles.stepper} data-orientation={orientation} aria-label="Flow stages">
      {steps.map((step, i) => (
        <GateStepRow
          key={step.state}
          step={step}
          isLast={i === steps.length - 1}
          active={step.state === selectedState}
          onSelect={onSelect}
        />
      ))}
    </ol>
  )
}
