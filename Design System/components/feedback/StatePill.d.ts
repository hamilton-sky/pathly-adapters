import * as React from 'react'

/**
 * Pathly StatePill — the FSM pipeline-stage pill. Coloured dot + uppercase
 * label, tinted to the stage colour. The core visual language of Pathly.
 *
 * @startingPoint section="Feedback" subtitle="FSM pipeline-stage pill (DONE / BUILDING / …)" viewport="700x150"
 */
export interface StatePillProps {
  /** Pipeline stage — drives the colour */
  state?: 'PLANNING' | 'BUILDING' | 'REVIEWING' | 'TESTING' | 'RETRO' | 'DONE' | 'ERROR' | 'IDLE'
  /** Override the visible text (defaults to the state name) */
  label?: string
  /** Solid fill instead of tint (for high-emphasis headers) */
  solid?: boolean
  style?: React.CSSProperties
}

export function StatePill(props: StatePillProps): JSX.Element
