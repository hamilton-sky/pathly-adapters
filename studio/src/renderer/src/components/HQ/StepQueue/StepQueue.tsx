import { useAutomationStore } from '../../../store/automationStore'
import type { AutomationStep } from '../../../types/automation'
import styles from '../ChatPanel.module.css'

export function StepQueue(): JSX.Element {
  const steps = useAutomationStore((s) => s.steps)
  const currentStepIndex = useAutomationStore((s) => s.currentStepIndex)
  const mode = useAutomationStore((s) => s.mode)
  const setStatus = useAutomationStore((s) => s.setStatus)
  const skipStep = useAutomationStore((s) => s.skipStep)
  const advanceToNext = useAutomationStore((s) => s.advanceToNext)

  async function handleApprove(step: AutomationStep): Promise<void> {
    try {
      const result = await window.pathly.automation.executeStep(step.action)
      if (result.success) {
        advanceToNext()
      } else {
        useAutomationStore.getState().setStatus('error')
        useAutomationStore.getState().setStepError(step.id, result.error ?? 'Step failed')
      }
    } catch (err) {
      useAutomationStore.getState().setStatus('error')
    }
  }

  if (steps.length === 0) return <></>

  if (mode === 'auto') {
    const doneCount = steps.filter((s) => s.status === 'done' || s.status === 'approved').length
    const pct = Math.round((doneCount / steps.length) * 100)
    return (
      <div className={styles.stepQueue}>
        <div className={styles.autoHeader}>
          <span className={styles.autoCount}>{doneCount} / {steps.length} steps</span>
          <button type="button" className={styles.automationBtnStop} onClick={() => setStatus('paused')}>
            &#9632; Stop
          </button>
        </div>
        <progress className={styles.autoProgress} value={pct} max={100} />
      </div>
    )
  }

  return (
    <div className={styles.stepQueue}>
      {steps.map((step, index) => {
        const isCurrent = index === currentStepIndex && step.status === 'pending'
        const isDone = step.status === 'done' || step.status === 'approved'
        const isSkipped = step.status === 'skipped'
        const isError = step.status === 'error'

        return (
          <div
            key={step.id}
            className={`${styles.stepItem} ${isCurrent ? styles.stepItemCurrent : ''} ${isDone ? styles.stepItemDone : ''} ${isSkipped ? styles.stepItemSkipped : ''}`}
          >
            <div className={`${styles.stepRow} ${isCurrent ? styles.stepRowSpaced : ''}`}>
              <span className={styles.stepIndex}>{index + 1}.</span>
              <span className={styles.stepDesc}>{step.description}</span>
              {isDone && <span className={styles.stepStatusDone}>&#10003;</span>}
              {isSkipped && <span className={styles.stepStatusSkipped}>&rarr;</span>}
            </div>

            <div className={`${styles.stepAction} ${isCurrent ? styles.stepActionSpaced : ''}`}>
              {step.action.type} &apos;{step.action.label}&apos;
            </div>

            {isError && step.errorMessage && (
              <div className={styles.stepError}>{step.errorMessage}</div>
            )}

            {isCurrent && (
              <div className={styles.stepActionBtns}>
                <button
                  type="button"
                  className={styles.automationBtnApprove}
                  onClick={() => void handleApprove(step)}
                >
                  &#10003; Approve
                </button>
                <button
                  type="button"
                  className={styles.automationBtnSkipStep}
                  onClick={() => skipStep(step.id)}
                >
                  &rarr; Skip
                </button>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
