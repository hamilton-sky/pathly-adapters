import { useTheme } from '../../useTheme'
import styles from './ChatPanel.module.css'

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
  const t = useTheme()

  return (
    <div
      className={styles.automationCard}
      style={{
        background: t.bgSurface0,
        border: `1.5px solid ${t.accent}44`,
        color: t.textPrimary,
        fontFamily: t.fontFamilyBase,
      }}
    >
      <div
        style={{
          fontSize: t.fontSizeBase,
          fontWeight: 600,
          marginBottom: 4,
          color: t.textPrimary,
        }}
      >
        {intent}
      </div>
      <div
        style={{
          fontSize: t.fontSizeSm,
          color: t.textSecondary,
          marginBottom: 10,
        }}
      >
        {stepCount} steps planned
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          className={styles.automationBtnRun}
          style={{
            background: schemaAvailable ? t.accent : t.bgSurface1,
            color: schemaAvailable ? '#fff' : t.textMuted,
            cursor: schemaAvailable ? 'pointer' : 'not-allowed',
            fontFamily: t.fontFamilyBase,
          }}
          disabled={!schemaAvailable}
          title={!schemaAvailable ? 'Studio schema unavailable' : undefined}
          onClick={onRunAll}
        >
          ▶ Run All
        </button>
        <button
          className={styles.automationBtnStep}
          style={{
            color: t.textPrimary,
            borderColor: t.borderSubtle,
            fontFamily: t.fontFamilyBase,
          }}
          onClick={onStepByStep}
        >
          Step by Step
        </button>
      </div>
    </div>
  )
}
