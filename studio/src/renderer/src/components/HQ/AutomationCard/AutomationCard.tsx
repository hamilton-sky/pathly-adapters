import styles from '../index.module.css'

interface AutomationCardProps {
  intent: string
  stepCount: number
  onRunAll: () => void
  onStepByStep: () => void
  schemaAvailable: boolean
}

export function AutomationCard({
  intent,
  stepCount,
  onRunAll,
  onStepByStep,
  schemaAvailable,
}: AutomationCardProps): JSX.Element {
  return (
    <div className={styles.automationCard}>
      <div className={styles.automationCardTitle}>
        {intent}
      </div>
      <div className={styles.automationCardSteps}>
        {stepCount} steps planned
      </div>
      <div className={styles.automationCardActions}>
        <button
          type="button"
          className={`${styles.automationBtnRun} ${schemaAvailable ? styles.automationBtnRunEnabled : ''}`}
          disabled={!schemaAvailable}
          title={!schemaAvailable ? 'Studio schema unavailable' : undefined}
          onClick={onRunAll}
        >
          ▶ Run All
        </button>
        <button
          type="button"
          className={styles.automationBtnStep}
          onClick={onStepByStep}
        >
          Step by Step
        </button>
      </div>
    </div>
  )
}
