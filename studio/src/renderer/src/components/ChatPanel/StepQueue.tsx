import { useAutomationStore } from '../../store/automationStore'
import type { AutomationStep } from '../../store/automationStore'
import { useTheme } from '../../useTheme'
import styles from './ChatPanel.module.css'

export function StepQueue(): JSX.Element {
  const steps = useAutomationStore((s) => s.steps)
  const currentStepIndex = useAutomationStore((s) => s.currentStepIndex)
  const mode = useAutomationStore((s) => s.mode)
  const setStatus = useAutomationStore((s) => s.setStatus)
  const skipStep = useAutomationStore((s) => s.skipStep)
  const advanceToNext = useAutomationStore((s) => s.advanceToNext)
  const t = useTheme()

  async function handleApprove(step: AutomationStep): Promise<void> {
    try {
      const result = await window.pathly.automation.executeStep(step.action)
      if (result.success) {
        advanceToNext()
      } else {
        useAutomationStore.getState().setStatus('error')
        const { steps: current } = useAutomationStore.getState()
        useAutomationStore.setState({
          steps: current.map((s) =>
            s.id === step.id ? { ...s, status: 'error', errorMessage: result.error ?? 'Step failed' } : s
          ),
        })
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
      <div
        className={styles.stepQueue}
        style={{ background: t.bgSurface0, fontFamily: t.fontFamilyBase }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: 8,
          }}
        >
          <span style={{ fontSize: t.fontSizeSm, color: t.textSecondary }}>
            {doneCount} / {steps.length} steps
          </span>
          <button
            className={styles.automationBtnStop}
            style={{
              color: t.red,
              borderColor: t.red,
              fontFamily: t.fontFamilyBase,
            }}
            onClick={() => setStatus('paused')}
          >
            &#9632; Stop
          </button>
        </div>
        <div className={styles.progressBar} style={{ background: t.bgSurface1 }}>
          <div
            className={styles.progressFill}
            style={{ width: `${pct}%`, background: t.accent }}
          />
        </div>
      </div>
    )
  }

  return (
    <div
      className={styles.stepQueue}
      style={{ background: t.bgSurface0, fontFamily: t.fontFamilyBase }}
    >
      {steps.map((step, index) => {
        const isCurrent = index === currentStepIndex && step.status === 'pending'
        const isDone = step.status === 'done' || step.status === 'approved'
        const isSkipped = step.status === 'skipped'
        const isError = step.status === 'error'

        return (
          <div
            key={step.id}
            className={`${styles.stepItem} ${isCurrent ? styles.stepItemCurrent : ''} ${isDone ? styles.stepItemDone : ''}`}
            style={{
              background: isCurrent ? t.bgSurface1 : t.bgSurface0,
              opacity: isDone || isSkipped ? 0.5 : 1,
              color: t.textPrimary,
              border: `1px solid ${isCurrent ? t.accent + '66' : t.borderSubtle}`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: isCurrent ? 8 : 0 }}>
              <span
                style={{
                  fontSize: t.fontSizeSm,
                  color: t.textMuted,
                  minWidth: 20,
                }}
              >
                {index + 1}.
              </span>
              <span style={{ flex: 1, fontSize: t.fontSizeSm, color: t.textPrimary }}>
                {step.description}
              </span>
              {isDone && (
                <span style={{ color: t.green, fontSize: t.fontSizeSm, fontWeight: 700 }}>
                  &#10003;
                </span>
              )}
              {isSkipped && (
                <span style={{ color: t.textMuted, fontSize: t.fontSizeSm }}>
                  &rarr;
                </span>
              )}
            </div>

            <div
              style={{
                fontSize: '11px',
                color: t.textMuted,
                fontFamily: t.fontFamilyMono,
                marginBottom: isCurrent ? 8 : 0,
                marginLeft: 28,
              }}
            >
              {step.action.type} &apos;{step.action.label}&apos;
            </div>

            {isError && step.errorMessage && (
              <div
                style={{
                  fontSize: t.fontSizeSm,
                  color: t.red,
                  marginLeft: 28,
                  marginTop: 4,
                }}
              >
                {step.errorMessage}
              </div>
            )}

            {isCurrent && (
              <div style={{ display: 'flex', gap: 6, marginLeft: 28 }}>
                <button
                  className={styles.automationBtnApprove}
                  style={{ background: t.green, color: '#fff', fontFamily: t.fontFamilyBase }}
                  onClick={() => void handleApprove(step)}
                >
                  &#10003; Approve
                </button>
                <button
                  className={styles.automationBtnSkipStep}
                  style={{
                    color: t.textSecondary,
                    borderColor: t.borderSubtle,
                    fontFamily: t.fontFamilyBase,
                  }}
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
