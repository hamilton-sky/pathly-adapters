import * as React from 'react'

/**
 * Pathly Badge — small monospace chip, tinted from a single colour.
 * Use for counts, categories, IDs, integration tags.
 *
 * @startingPoint section="Feedback" subtitle="Tinted monospace chip / count badge" viewport="700x150"
 */
export interface BadgeProps {
  /** Chip text (or pass children) */
  label?: React.ReactNode
  children?: React.ReactNode
  /** Any CSS colour / token, e.g. "var(--green)". Overrides variant. */
  color?: string
  /** Semantic preset */
  variant?: 'core' | 'flow' | 'integration' | 'body' | 'neutral'
  style?: React.CSSProperties
}

export function Badge(props: BadgeProps): JSX.Element
