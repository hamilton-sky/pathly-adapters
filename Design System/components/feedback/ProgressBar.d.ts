import * as React from 'react'

/**
 * Pathly ProgressBar — thin rounded track + coloured fill, optional fraction label.
 */
export interface ProgressBarProps {
  /** Current value */
  value: number
  /** @default 100 */
  max?: number
  /** Fill colour / token. @default "var(--accent)" */
  color?: string
  /** Track height in px. @default 6 */
  height?: number
  /** Trailing label, e.g. "3/3" */
  label?: React.ReactNode
  style?: React.CSSProperties
}

export function ProgressBar(props: ProgressBarProps): JSX.Element
