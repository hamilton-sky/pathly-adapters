import { formatTokens, usagePercent } from '../../ContextManifest/manifestUtils'
import styles from './TokenMeter.module.css'

interface Props {
  /** Estimated board-context tokens for the next question. */
  contextTokens: number
  /** What offering the enabled actions to the model costs. */
  actionTokens: number
  /** Ticked sections with no measured size yet. */
  unmeasured: number
  budget: number
}

/** The popover's one shared meter: what the next question will spend of the
 *  context budget. Shared by both tabs because everything sent spends it. */
export function TokenMeter({ contextTokens, actionTokens, unmeasured, budget }: Props): JSX.Element {
  const total = contextTokens + actionTokens
  const over = total > budget
  return (
    <div className={styles.meter} data-over={over ? 'true' : 'false'}>
      <progress
        className={styles.bar}
        value={usagePercent(total, budget)}
        max={100}
        aria-label="Estimated context tokens of the budget"
      />
      <div className={styles.text}>
        ≈ {formatTokens(total)} of {formatTokens(budget)} tokens
        {actionTokens > 0 && <span className={styles.muted}> · actions {formatTokens(actionTokens)}</span>}
        {unmeasured > 0 && <span className={styles.muted}> · +{unmeasured} not measured yet</span>}
      </div>
      {over && <div className={styles.warn}>Over budget: the lowest-priority board sections will be cut.</div>}
    </div>
  )
}
