import * as React from 'react'

/**
 * Pathly Tabs — horizontal tab bar with optional count badges.
 *
 * @startingPoint section="Navigation" subtitle="Underline / pill tab bar with count badges" viewport="700x150"
 */
export interface TabItem {
  id: string
  label: React.ReactNode
  /** Optional count badge */
  count?: number | string
}
export interface TabsProps {
  tabs: TabItem[]
  /** Currently selected tab id */
  activeId: string
  onChange?: (id: string) => void
  /** "underline" for in-panel tabs, "pill" for top-level switch. @default "underline" */
  variant?: 'underline' | 'pill'
  style?: React.CSSProperties
}

export function Tabs(props: TabsProps): JSX.Element
