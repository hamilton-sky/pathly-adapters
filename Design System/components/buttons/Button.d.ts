import * as React from 'react'

/**
 * Pathly Button — the app-wide action button. Accent-tinted by default;
 * use `cta` for the one high-emphasis action per view and `secondary`
 * for toolbar/control-bar buttons.
 *
 * @startingPoint section="Buttons" subtitle="Accent-tinted action button with variants & sizes" viewport="700x140"
 */
export interface ButtonProps {
  /** Button label / content */
  children?: React.ReactNode
  /** Visual emphasis. @default "primary" */
  variant?: 'primary' | 'cta' | 'secondary' | 'ghost' | 'destructive'
  /** @default "md" */
  size?: 'sm' | 'md'
  disabled?: boolean
  /** Shows a spinner and blocks interaction */
  loading?: boolean
  /** Leading icon node (e.g. a lucide icon) */
  icon?: React.ReactNode
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void
  type?: 'button' | 'submit' | 'reset'
  style?: React.CSSProperties
}

export function Button(props: ButtonProps): JSX.Element
