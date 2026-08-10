import { AdapterBadge } from '../../EngineBoard'
import { KindBadge } from '../../../RunDetailPage/KindBadge/KindBadge'
import { StatusBadge } from '../../../RunDetailPage/StatusBadge/StatusBadge'
import { adapterFromProvider } from '../../../RunDetailPage/runAdapter'
import { formatRelative } from '../../../../utils/timestamp'
import type { RunSummary } from '../types'
import s from './RunCard.module.css'

interface Props {
  run: RunSummary
  onOpen?: (runId: string) => void
}

const fmtCost = (c: number): string => (c > 0 ? `$${c.toFixed(3)}` : '$0')
const fmtTok = (t: number): string => (t >= 1000 ? `${(t / 1000).toFixed(1)}k` : String(t || 0))

// Card variant of RunRow for Runs-mode 'grid' view — mirrors the Live board's RECENT engine cards
// (kind/adapter top · feature name · sub · tokens/cost/age footer). Same data + click-to-open as
// RunRow; only the layout differs, so the grid/list toggle swaps between them.
export function RunCard({ run: r, onOpen }: Props): JSX.Element {
  const adapter = adapterFromProvider(r.adapter)
  const ts = r.finished_at || r.started_at
  const showStages = (r.kind === 'flow' || r.kind === 'decompose') && !!r.stage_count
  const sub = showStages ? `${r.stage_count} stages` : r.status

  return (
    <button type="button" className={s.card} onClick={() => onOpen?.(r.run_id)}>
      <div className={s.top}>
        <KindBadge kind={r.kind} />
        {adapter && <AdapterBadge adapter={adapter} />}
        <span className={s.spacer} />
        <StatusBadge status={r.status} />
      </div>
      <div className={s.name}>{r.feature}</div>
      <div className={s.sub}>{sub}</div>
      <div className={s.foot}>
        <span className={s.tok}>{fmtTok(r.tokens_total)} tok</span>
        <span className={s.cost} {...(r.cost_usd > 0 ? {} : { 'data-zero': '' })}>{fmtCost(r.cost_usd)}</span>
        <span className={s.spacer} />
        <span className={s.time}>{ts ? formatRelative(ts) : '—'}</span>
      </div>
    </button>
  )
}
