import { useRunCost } from '../hooks/useRunCost'
import s from './RunCostBadge.module.css'

interface Props {
  feature: string | null
}

// A slim readout of the active feature's most-recent pipeline run cost — the settled,
// billing-reconciled per-flow total from GET /db/runs/<run_id>/cost (unlike the engine cards,
// which show '-' while live). Hidden until a run with real cost/tokens exists for this feature.
export function RunCostBadge({ feature }: Props): JSX.Element | null {
  const { cost } = useRunCost(feature)
  if (!cost || (cost.cost_usd === 0 && cost.tokens_total === 0)) return null

  const tok =
    cost.tokens_total >= 1000
      ? `${(cost.tokens_total / 1000).toFixed(1)}k`
      : String(cost.tokens_total)

  return (
    <div className={s.badge} title="Settled cost for this feature's most recent pipeline run">
      <span className={s.label}>Run cost</span>
      <span className={s.cost}>${cost.cost_usd.toFixed(3)}</span>
      <span className={s.tokens}>{tok} tok</span>
      <span className={s.meta}>{cost.invocations} agents</span>
    </div>
  )
}
