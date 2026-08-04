import { RunRow } from './RunRow/RunRow'
import type { RunSummary } from './types'
import s from './RunList.module.css'

interface Props {
  /** Already filtered by the active category / adapter / scope. */
  runs: RunSummary[]
  loading: boolean
  /** True when the project has ANY runs pre-filter (distinguishes "none yet" from "filtered out"). */
  hasAny: boolean
  onOpenRun?: (runId: string) => void
}

// The folded run list (Runs mode): a flat, newest-first list of top-level runs — deliberately NOT
// grouped into category sections like the Live board, so the two modes read as distinct surfaces.
export function RunList({ runs, loading, hasAny, onOpenRun }: Props): JSX.Element {
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
  return (
    <div className={s.list}>
      {runs.map((r) => (
        <RunRow key={r.run_id} run={r} onOpen={onOpenRun} />
      ))}
    </div>
  )
}
