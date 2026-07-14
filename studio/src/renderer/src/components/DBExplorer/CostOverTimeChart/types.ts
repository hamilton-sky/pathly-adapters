// Shared types for the CostOverTimeChart component.

export interface CostPoint {
  /** ISO date "YYYY-MM-DD" (preferred) or already-short "MM/DD". */
  day: string
  /** Reported cost in USD for that day. */
  cost_usd: number
  /** Total tokens for that day. */
  tokens: number
  /** Number of spans recorded that day. */
  span_count: number
}

export type RangeDays = 7 | 14 | 30

export type ScaleMode = 'linear' | 'log'
