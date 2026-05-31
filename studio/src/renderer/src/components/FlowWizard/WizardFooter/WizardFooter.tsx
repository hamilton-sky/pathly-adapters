import React from 'react'
import { Button } from '../../ui'
import styles from './WizardFooter.module.css'

interface WizardFooterProps {
  step: number
  totalSteps: number
  onCancel: () => void
  onBack: () => void
  onNext: () => void
  onSave: () => void
  saving: boolean
  nextDisabled?: boolean
}

export function WizardFooter({
  step,
  totalSteps,
  onCancel,
  onBack,
  onNext,
  onSave,
  saving,
  nextDisabled,
}: WizardFooterProps): JSX.Element {
  const isNextDisabled = saving || !!nextDisabled

  return (
    <div className={styles.row}>
      <button className={`${styles.btn} ${styles.cancel}`} onClick={onCancel} data-testid="wizard-btn-cancel">Cancel</button>
      <div className={styles.group}>
        {step > 0 && <button className={`${styles.btn} ${styles.back}`} onClick={onBack} data-testid="wizard-btn-back">← Back</button>}
        {step < totalSteps ? (
          <button className={`${styles.btn} ${styles.next}`} onClick={onNext} disabled={isNextDisabled} data-testid="wizard-btn-next">
            Next →
          </button>
        ) : (
          <Button onClick={onSave} loading={saving} disabled={saving} data-testid="wizard-btn-save">
            Save Flow
          </Button>
        )}
      </div>
    </div>
  )
}
