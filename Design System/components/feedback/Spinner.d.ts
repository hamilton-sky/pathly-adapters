import * as React from 'react'

/** Pathly Spinner — small rotating ring for inline loading states. */
export interface SpinnerProps {
  /** px. @default 14 */
  size?: number
  /** Arc colour. @default "var(--accent)" */
  color?: string
  /** @default 2 */
  strokeWidth?: number
  style?: React.CSSProperties
}

export function Spinner(props: SpinnerProps): JSX.Element
