import React from 'react'

interface WizardFooterProps {
  step: number
  onCancel: () => void
  onBack: () => void
  onNext: () => void
  onSave: () => void
  saving: boolean
  styles: Record<string, React.CSSProperties>
}

export function WizardFooter({
  step,
  onCancel,
  onBack,
  onNext,
  onSave,
  saving,
  styles
}: WizardFooterProps): JSX.Element {
  const saveNextStyle: React.CSSProperties = saving
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
          <button style={saveNextStyle} onClick={onNext} disabled={saving}>
            Next →
          </button>
        ) : (
          <button style={saveNextStyle} onClick={onSave} disabled={saving}>
            {saving ? 'Saving…' : 'Save Flow'}
          </button>
        )}
      </div>
    </div>
  )
}
