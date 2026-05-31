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
      <button className={`${styles.btn} ${styles.cancel}`} onClick={onCancel}>Cancel</button>
      <div className={styles.group}>
        {step > 0 && <button className={`${styles.btn} ${styles.back}`} onClick={onBack}>← Back</button>}
        {step < totalSteps ? (
          <button className={`${styles.btn} ${styles.next}`} onClick={onNext} disabled={isNextDisabled}>
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
