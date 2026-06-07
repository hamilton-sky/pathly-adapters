import * as React from 'react'

/**
 * Pathly IconButton — square, icon-only control used across the topbar,
 * panel toolbars and row actions. Always pair with a title for tooltip/a11y.
 */
export interface IconButtonProps {
  /** Icon node (lucide icon at size 14–15 recommended) */
  children: React.ReactNode
  /** Accessible label / tooltip text — required */
  title: string
  /** @default "default" */
  variant?: 'default' | 'danger' | 'muted'
  /** @default "sm" */
  size?: 'sm' | 'md'
  /** Renders the pressed / selected state */
  active?: boolean
  disabled?: boolean
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void
  style?: React.CSSProperties
}

export function IconButton(props: IconButtonProps): JSX.Element
