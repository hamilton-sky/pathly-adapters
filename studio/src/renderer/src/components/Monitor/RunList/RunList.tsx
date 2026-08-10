import { RunRow } from './RunRow/RunRow'
import { RunCard } from './RunCard/RunCard'
import type { RunSummary } from './types'
import s from './RunList.module.css'

interface Props {
  /** Already filtered by the active category / adapter / scope. */
  runs: RunSummary[]
  loading: boolean
  /** True when the project has ANY runs pre-filter (distinguishes "none yet" from "filtered out"). */
  hasAny: boolean
  /** Same layout toggle the Live board uses: 'grid' = cards, 'banner' = the flat row list. */
  view?: 'grid' | 'banner'
  onOpenRun?: (runId: string) => void
}

// The folded run list (Runs mode): top-level runs, newest-first. Honors the header's grid/list
// layout toggle (like the Live board) — 'grid' renders RunCards in a responsive grid, 'banner'
// the flat RunRow list.
export function RunList({ runs, loading, hasAny, view = 'banner', onOpenRun }: Props): JSX.Element {
  if (loading && runs.length === 0) {
    return <div className={s.state}>Loading…</div>
  }
  if (runs.length === 0) {
    return (
      <div className={s.state}>
        {hasAny ? 'No runs match this view.' : 'No runs recorded for this project yet.'}
      </div>
    )
  }
  if (view === 'grid') {
    return (
      <div className={s.grid}>
        {runs.map((r) => (
          <RunCard key={r.run_id} run={r} onOpen={onOpenRun} />
        ))}
      </div>
    )
  }
  return (
    <div className={s.list}>
      {runs.map((r) => (
        <RunRow key={r.run_id} run={r} onOpen={onOpenRun} />
      ))}
    </div>
  )
}
