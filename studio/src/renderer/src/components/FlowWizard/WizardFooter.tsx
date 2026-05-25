import React from 'react'
import { Button } from '../ui'

interface WizardFooterProps {
  step: number
  onCancel: () => void
  onBack: () => void
  onNext: () => void
  onSave: () => void
  saving: boolean
  nextDisabled?: boolean
  styles: Record<string, React.CSSProperties>
}

export function WizardFooter({
  step,
  onCancel,
  onBack,
  onNext,
  onSave,
  saving,
  nextDisabled,
  styles
}: WizardFooterProps): JSX.Element {
  const isNextDisabled = saving || !!nextDisabled
  const saveNextStyle: React.CSSProperties = isNextDisabled
    ? { ...styles.nextBtn, opacity: 0.6, cursor: 'not-allowed' }
    : styles.nextBtn

  return (
    <div style={styles.btnRow}>
      <button style={styles.cancelBtn} onClick={onCancel}>Cancel</button>
      <div style={{ display: 'flex', gap: '8px' }}>
        {step > 1 && (
          <button style={styles.backBtn} onClick={onBack}>← Back</button>
        )}
        {step < 5 ? (
          <button style={saveNextStyle} onClick={onNext} disabled={isNextDisabled}>
            Next →
          </button>
        ) : (
          <Button onClick={onSave} loading={saving} disabled={saving}>
            Save Flow
          </Button>
        )}
      </div>
    </div>
  )
}
