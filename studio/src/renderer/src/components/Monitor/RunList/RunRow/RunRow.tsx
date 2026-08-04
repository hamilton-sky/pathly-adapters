import { AdapterBadge } from '../../EngineBoard'
import { KindBadge } from '../../../RunDetailPage/KindBadge/KindBadge'
import { StatusBadge } from '../../../RunDetailPage/StatusBadge/StatusBadge'
import { adapterFromProvider } from '../../../RunDetailPage/runAdapter'
import { formatRelative } from '../../../../utils/timestamp'
import type { RunSummary } from '../types'
import s from './RunRow.module.css'

interface Props {
  run: RunSummary
  onOpen?: (runId: string) => void
}

const fmtCost = (c: number): string => (c > 0 ? `$${c.toFixed(3)}` : '$0')

// One folded run: kind · feature (+ "N stages" for flow/decompose) · adapter · status · cost · when.
// Reuses RunDetailPage's KindBadge/StatusBadge (they carry decompose/error/aborted, which Monitor's
// unions don't) and the shared AdapterBadge. Clicking opens the run's RunDetailPage.
export function RunRow({ run: r, onOpen }: Props): JSX.Element {
  const adapter = adapterFromProvider(r.adapter)
  const ts = r.finished_at || r.started_at
  const showStages = (r.kind === 'flow' || r.kind === 'decompose') && !!r.stage_count

  return (
    <button type="button" className={s.row} onClick={() => onOpen?.(r.run_id)}>
      <KindBadge kind={r.kind} />
      <span className={s.feature}>
        <span className={s.name}>{r.feature}</span>
        {showStages && <span className={s.sub}>· {r.stage_count} stages</span>}
      </span>
      {adapter && <AdapterBadge adapter={adapter} />}
      <StatusBadge status={r.status} />
      <span className={s.spacer} />
      <span className={s.cost} {...(r.cost_usd > 0 ? {} : { 'data-zero': '' })}>{fmtCost(r.cost_usd)}</span>
      <span className={s.time}>{ts ? formatRelative(ts) : '—'}</span>
    </button>
  )
}
