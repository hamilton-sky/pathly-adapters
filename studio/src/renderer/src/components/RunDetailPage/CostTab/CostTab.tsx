import { StagePill } from '../../Monitor/EngineBoard'
import type { RunDetailCost, RunDetailStage } from '../types'
import s from './CostTab.module.css'

interface Props {
  cost: RunDetailCost
  stages: RunDetailStage[]
}

const fmtCost = (c: number): string => (c > 0 ? `$${c.toFixed(3)}` : '$0')
const fmtTok = (t: number): string =>
  t >= 1000 ? `${(t / 1000).toFixed(1)}k` : String(t || 0)

// Cost tab: the run's headline readout + a per-stage table, so the parity contract (run total ==
// sum of stages, reconciled from agent_invocations) is legible at a glance.
export function CostTab({ cost, stages }: Props): JSX.Element {
  return (
    <div className={s.wrap}>
      <div className={s.readout}>
        <span className={s.big}>{fmtCost(cost.cost_usd)}</span>
        <span className={s.sub}>
          {fmtTok(cost.tokens_total)} tok · {cost.invocations} agent{cost.invocations === 1 ? '' : 's'}
        </span>
      </div>

      {stages.length > 0 && (
        <div className={s.tableWrap}>
          <table className={s.table}>
            <thead>
              <tr>
                <th>Stage</th>
                <th className={s.num}>Tokens</th>
                <th className={s.num}>Cost</th>
              </tr>
            </thead>
            <tbody>
              {stages.map((st, i) => (
                <tr key={`${st.run_id}-${i}`}>
                  <td><StagePill stage={st.stage ?? ''} /></td>
                  <td className={s.num}>{fmtTok(st.tokens)}</td>
                  <td className={s.num}>{fmtCost(st.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
