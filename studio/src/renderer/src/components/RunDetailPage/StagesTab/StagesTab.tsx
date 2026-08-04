import { AdapterBadge, StagePill } from '../../Monitor/EngineBoard'
import { StatusBadge } from '../StatusBadge/StatusBadge'
import { adapterFromProvider } from '../runAdapter'
import type { RunDetailStage } from '../types'
import s from './StagesTab.module.css'

interface Props {
  stages: RunDetailStage[]
  /** Click-through to the Logs tab (HANDOFF §E: a stage row jumps to its logs). */
  onOpenStage?: (stage: string | null) => void
}

const fmtCost = (c: number): string => (c > 0 ? `$${c.toFixed(3)}` : '—')
const fmtTok = (t: number): string =>
  t >= 1000 ? `${(t / 1000).toFixed(1)}k` : t ? String(t) : '—'

// Stages tab: one row per stage — a single/loop run has one; a flow folds its per-stage runs in.
// Local rows per HANDOFF §E (deriveFlowSteps doesn't fit: no FSM events, and StepStatus can't
// express a failed stage without editing Monitor).
export function StagesTab({ stages, onOpenStage }: Props): JSX.Element {
  if (stages.length === 0) {
    return <div className={s.empty}>No stages recorded for this run.</div>
  }
  return (
    <div className={s.list}>
      {stages.map((st, i) => {
        const adapter = adapterFromProvider(st.adapter)
        return (
          <button
            key={`${st.run_id}-${i}`}
            type="button"
            className={s.row}
            onClick={() => onOpenStage?.(st.stage)}
          >
            <StagePill stage={st.stage ?? ''} />
            <StatusBadge status={st.status} />
            {adapter && <AdapterBadge adapter={adapter} />}
            <span className={s.spacer} />
            <span className={s.tok}>{fmtTok(st.tokens)} tok</span>
            <span className={s.cost} {...(st.cost_usd > 0 ? {} : { 'data-zero': '' })}>
              {fmtCost(st.cost_usd)}
            </span>
          </button>
        )
      })}
    </div>
  )
}
