import * as React from 'react'

/**
 * Pathly Tooltip — hover label on a wrapped trigger; optional description & shortcut.
 */
export interface TooltipProps {
  /** Tooltip title */
  label: React.ReactNode
  /** Secondary description line */
  description?: string
  /** Keyboard shortcut shown as a kbd chip */
  shortcut?: string
  /** @default "bottom" */
  placement?: 'top' | 'bottom' | 'left' | 'right'
  /** The trigger element */
  children: React.ReactNode
  style?: React.CSSProperties
}

export function Tooltip(props: TooltipProps): JSX.Element
