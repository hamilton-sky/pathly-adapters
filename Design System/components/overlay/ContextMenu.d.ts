import * as React from 'react'

/**
 * Pathly ContextMenu — floating menu surface of action rows.
 */
export interface ContextMenuItem {
  label?: React.ReactNode
  icon?: React.ReactNode
  onClick?: () => void
  /** Renders the row in red (destructive) */
  danger?: boolean
  shortcut?: string
  /** Render a divider instead of a row */
  separator?: boolean
}
export interface ContextMenuProps {
  items: ContextMenuItem[]
  style?: React.CSSProperties
}

export function ContextMenu(props: ContextMenuProps): JSX.Element
