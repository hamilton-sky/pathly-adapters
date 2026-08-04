import { formatClock } from '../../../utils/timestamp'
import type { RunDetailArtifact, RunDetailBoardPost } from '../types'
import s from './BoardTab.module.css'

interface Props {
  board: RunDetailBoardPost[]
  artifacts: RunDetailArtifact[]
}

// Board tab: posts correlated to this run (run_id when stamped, else the P0 time-window fallback)
// and their artifacts. Empty posts → an explicit line (AC-3). Artifacts are metadata only —
// title / type / path, NO hydrate (AC-4), so a non-md artifact never mojibakes.
export function BoardTab({ board, artifacts }: Props): JSX.Element {
  return (
    <div className={s.wrap}>
      <section className={s.section}>
        <div className={s.label}>Board posts</div>
        {board.length === 0 ? (
          <div className={s.empty}>No board posts correlated to this run.</div>
        ) : (
          <div className={s.posts}>
            {board.map((p) => (
              <div key={p.id} className={s.post}>
                <span className={s.meta}>
                  {p.from_agent || 'agent'} · {p.type || 'note'}
                  {p.ts ? ` · ${formatClock(p.ts)}` : ''}
                </span>
                <span className={s.text}>{p.text}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {artifacts.length > 0 && (
        <section className={s.section}>
          <div className={s.label}>Artifacts</div>
          <div className={s.artifacts}>
            {artifacts.map((a, i) => (
              <div key={i} className={s.artifact}>
                <span className={s.aTitle}>{a.title || a.path || 'artifact'}</span>
                {a.type && <span className={s.aType}>{a.type}</span>}
                {a.path && <span className={s.aPath}>{a.path}</span>}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
