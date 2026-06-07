import * as React from 'react'

/**
 * Pathly Card — standard surface container with optional header (title + actions).
 *
 * @startingPoint section="Surface" subtitle="Surface container with header & actions" viewport="700x260"
 */
export interface CardProps {
  /** Header title (omit for a plain surface) */
  title?: React.ReactNode
  /** Right-aligned header actions (buttons, badges) */
  actions?: React.ReactNode
  children?: React.ReactNode
  /** Adds hover lift + accent border for clickable cards */
  interactive?: boolean
  /** Body padding. @default "14px 16px" */
  padding?: string
  onClick?: (e: React.MouseEvent<HTMLDivElement>) => void
  style?: React.CSSProperties
}

export function Card(props: CardProps): JSX.Element
