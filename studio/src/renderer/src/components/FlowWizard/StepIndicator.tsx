import React from 'react'
import type { Theme } from '../../theme' 
import { stepDotStyle } from './FlowWizard.styles'

interface StepIndicatorProps {
  step: number
  t: Theme
  styles: Record<string, React.CSSProperties>
}

export function StepIndicator({ step, t, styles }: StepIndicatorProps): JSX.Element {
  return (
    <div style={styles.stepIndicator}>
      {[1, 2, 3, 4, 5, 6, 7, 8].map((n, i) => (
        <React.Fragment key={n}>
          <div style={stepDotStyle(t, step === n, step > n)}>
            {step > n ? '✓' : n}
          </div>
          {i < 7 && <div style={styles.stepConnector} />}
        </React.Fragment>
      ))}
    </div>
  )
}
