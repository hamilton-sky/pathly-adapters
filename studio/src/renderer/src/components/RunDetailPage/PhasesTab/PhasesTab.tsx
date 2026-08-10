import { formatClock } from '../../../utils/timestamp'
import type { RunDetailBoardPost } from '../types'
import s from './PhasesTab.module.css'

interface Props {
  phases: RunDetailBoardPost[]
}

// Phases tab: the run's PHASE_START/PHASE_DONE markers (type='phase' board posts, text
// "<phase> started|done") as a chronological timeline — the live pipeline-progress view, split out
// of the Board tab's decisions/discoveries. Streams in live once the phase post carries run_id
// (backend: _phase_board stamps the live run's run_id → the T3 per-run feed).
export function PhasesTab({ phases }: Props): JSX.Element {
  if (phases.length === 0) {
    return <div className={s.empty}>No phase markers recorded for this run yet.</div>
  }
  return (
    <ol className={s.list}>
      {phases.map((p) => {
        const done = / done$/.test(p.text || '')
        return (
          <li key={p.id} className={s.item}>
            <span className={s.dot} {...(done ? { 'data-done': '' } : {})} />
            <span className={s.text}>{p.text}</span>
            <span className={s.spacer} />
            <span className={s.agent}>{p.from_agent || 'agent'}</span>
            {p.ts && <span className={s.time}>{formatClock(p.ts)}</span>}
          </li>
        )
      })}
    </ol>
  )
}
