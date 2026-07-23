import { useMemo } from 'react'
import { useStore } from '../../../../store'
import { deriveFlowSteps } from '../flowSteps'
import { StepRow } from './StepRow'
import styles from './FlowStepper.module.css'

interface FlowStepperProps {
  onStageClick: (state: string) => void
}

/**
 * The running flow rendered as a vertical stepper. Reads the SAME store data as the (removed)
 * top FsmView — `pipelineStates` / `stageRoles` / `fsmState` / `events`, all hydrated by
 * useMonitorSession from the LIVE DB flow — so a user-created flow shows its real phases the
 * moment it's activated, with zero per-flow code.
 */
export function FlowStepper({ onStageClick }: FlowStepperProps): JSX.Element {
  const pipelineStates = useStore((s) => s.pipelineStates)
  const stageRoles = useStore((s) => s.stageRoles)
  const fsmState = useStore((s) => s.fsmState)
  const events = useStore((s) => s.events)

  const steps = useMemo(
    () => deriveFlowSteps(pipelineStates, stageRoles, fsmState, events),
    [pipelineStates, stageRoles, fsmState, events],
  )

  if (steps.length === 0) {
    return <p className={styles.empty}>No stages to show yet.</p>
  }

  return (
    <ol className={styles.stepper} aria-label="Flow stages">
      {steps.map((step, i) => (
        <StepRow
          key={step.state}
          step={step}
          index={i}
          isLast={i === steps.length - 1}
          onClick={onStageClick}
        />
      ))}
    </ol>
  )
}
