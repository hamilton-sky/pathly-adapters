import { Coins } from 'lucide-react'
import { formatTokens, formatUsd } from './promptCost'
import styles from './PromptCostMeter.module.css'

const DEFAULT_TITLE =
  'Rough estimate of the prompt (input) tokens and cost — about 4 chars per token at claude ' +
  "input rates. The model's output tokens (usually the larger share of run cost) can't be known " +
  'before the run, so actual cost is higher.'

interface Props {
  /** Estimated input tokens (already summed by the caller). */
  tokens: number
  /** Estimated input cost in USD (already summed by the caller). */
  cost: number
  /** Small leading label, e.g. 'flow' → "flow ≈ 42k tok · $0.12 input". Omit for none. */
  prefix?: string
  /** Override the explanatory hover text. */
  title?: string
}

/**
 * Compact, muted input-token + cost readout for a run/flow gate footer. Presentational only —
 * the caller estimates tokens/cost via ./promptCost and passes the totals in. Pins itself to the
 * LEFT of a flex-end footer (margin-right:auto) so action buttons stay right.
 */
export function PromptCostMeter({ tokens, cost, prefix, title }: Props): JSX.Element {
  return (
    <span className={styles.meter} title={title ?? DEFAULT_TITLE}>
      {prefix && <span className={styles.prefix}>{prefix}</span>}
      <Coins size={12} className={styles.icon} aria-hidden="true" />
      <span className={styles.tokens}>≈ {formatTokens(tokens)} tok</span>
      <span className={styles.sep}>·</span>
      <span className={styles.cost}>{formatUsd(cost)}</span>
      <span className={styles.hint}>input</span>
    </span>
  )
}
