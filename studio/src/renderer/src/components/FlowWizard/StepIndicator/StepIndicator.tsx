import React from 'react'
import styles from './StepIndicator.module.css'

interface StepIndicatorProps {
  step: number
  totalSteps: number
  onJumpToStep?: (step: number) => void
}

export function StepIndicator({ step, totalSteps, onJumpToStep }: StepIndicatorProps): JSX.Element {
  return (
    <div className={styles.root}>
      {Array.from({ length: totalSteps }, (_, idx) => {
        const n = idx + 1
        const active = step === n
        const done = step > n
        const dotClass = [styles.dot, active ? styles.dotActive : '', done ? styles.dotDone : ''].filter(Boolean).join(' ')
        return (
          <React.Fragment key={n}>
            <div
              className={dotClass}
              onClick={done && onJumpToStep ? () => onJumpToStep(n) : undefined}
            >
              {done ? '✓' : n}
            </div>
            {idx < totalSteps - 1 && <div className={styles.connector} />}
          </React.Fragment>
        )
      })}
    </div>
  )
}
