import React from 'react'
import type { Theme } from '../../../theme'
import { stepDotStyle } from '../FlowWizard.styles'

interface StepIndicatorProps {
  step: number
  totalSteps: number
  onJumpToStep?: (step: number) => void
  t: Theme
  styles: Record<string, React.CSSProperties>
}

export function StepIndicator({ step, totalSteps, onJumpToStep, t, styles }: StepIndicatorProps): JSX.Element {
  return (
    <div style={styles.stepIndicator}>
      {Array.from({ length: totalSteps }, (_, idx) => {
        const n = idx + 1
        const active = step === n
        const done = step > n
        return (
          <React.Fragment key={n}>
            <div
              style={stepDotStyle(t, active, done)}
              onClick={done && onJumpToStep ? () => onJumpToStep(n) : undefined}
            >
              {done ? '✓' : n}
            </div>
            {idx < totalSteps - 1 && <div style={styles.stepConnector} />}
          </React.Fragment>
        )
      })}
    </div>
  )
}
