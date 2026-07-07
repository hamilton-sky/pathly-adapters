import { Timestamp } from '../../../../Timestamp/Timestamp'
import { computeRollup } from '../../GoalsView/goalsViewUtils'
import { HoverCard } from '../HoverCard/HoverCard'
import { TileDeleteButton } from '../TileDeleteButton/TileDeleteButton'
import { absoluteTime, firstLine } from '../format'
import type { Message } from '../../../types'
import hc from '../HoverCard/HoverCard.module.css'
import s from './GoalTile.module.css'

interface Props {
  goal: Message
  tasks: Message[]
  onOpen: (goalId: string) => void
  onDelete?: (goal: Message) => void
}

type GoalStatus = 'running' | 'blocked' | 'done' | 'idle'

// Goal sticker — the "anchor" of the board. Rolls up its tasks (reusing the same
// computeRollup as GoalsView) into a status dot + progress bar. Click → GoalDetailModal.
export function GoalTile({ goal, tasks, onOpen, onDelete }: Props): JSX.Element {
  const r = computeRollup(tasks)
  const status: GoalStatus =
    r.failed > 0 ? 'blocked' : r.running > 0 ? 'running' : r.total > 0 && r.done === r.total ? 'done' : 'idle'
  const pct = r.total > 0 ? Math.round((r.done / r.total) * 100) : 0
  const roll = r.total === 0 ? 'queued · 0 tasks' : `${r.total} task${r.total !== 1 ? 's' : ''} · ${r.done} done`
  const title = firstLine(goal.text)
  const full = absoluteTime(goal.ts)

  return (
    <HoverCard
      card={
        <>
          <div className={hc.pvHead}>
            <span className={hc.pvKind}>Goal</span>
            <span className={hc.pvTime}>{roll}</span>
          </div>
          <div className={hc.pvTitle}>{title}</div>
          <div className={hc.pvMeta}>{full}</div>
        </>
      }
    >
      <div
        role="button"
        tabIndex={0}
        className={s.tile}
        onClick={() => onOpen(goal.id)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onOpen(goal.id)
          }
        }}
      >
        <div className={s.top}>
          <span className={s.kind}>Goal</span>
          <span className={s.dot} data-status={status} />
          <span className={s.time} title={full}>
            <Timestamp value={goal.ts} />
          </span>
        </div>
        <div className={s.title}>{title}</div>
        <div className={s.footer}>
          <span className={s.bar}>
            {/* dynamic progress width — the one data-driven style, mirrors ProgressBar */}
            <span className={s.fill} style={{ width: `${pct}%` }} />
          </span>
          <span className={s.roll}>{roll}</span>
        </div>
        {onDelete && <TileDeleteButton onDelete={() => onDelete(goal)} />}
      </div>
    </HoverCard>
  )
}
