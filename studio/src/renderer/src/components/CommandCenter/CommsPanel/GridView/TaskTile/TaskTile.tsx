import { Timestamp } from '../../../../Timestamp/Timestamp'
import { HoverCard } from '../HoverCard/HoverCard'
import { TileDeleteButton } from '../TileDeleteButton/TileDeleteButton'
import { absoluteTime, firstLine } from '../format'
import type { Message } from '../../../types'
import hc from '../HoverCard/HoverCard.module.css'
import s from './TaskTile.module.css'

interface Props {
  task: Message
  onOpen: (task: Message) => void
  onDelete?: (task: Message) => void
}

const STATUS_LABEL: Record<string, string> = {
  pending: 'pending',
  in_progress: 'in progress',
  done: 'done',
  blocked: 'blocked',
  failed: 'failed',
}

// Task sticker — the smallest, one-line chip. Only UNGROUPED tasks reach this band
// (see gridBands); click routes to the goal DAG if one exists, else the message modal.
export function TaskTile({ task, onOpen, onDelete }: Props): JSX.Element {
  const status = task.taskStatus ?? 'pending'
  const title = firstLine(task.text)
  const full = absoluteTime(task.ts)

  return (
    <HoverCard
      card={
        <>
          <div className={hc.pvHead}>
            <span className={hc.pvKind}>Task</span>
            <span className={hc.pvTime}>{STATUS_LABEL[status] ?? status}</span>
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
        onClick={() => onOpen(task)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onOpen(task)
          }
        }}
      >
        <span className={s.dot} data-status={status} />
        <span className={s.title}>{title}</span>
        <span className={s.time} title={full}>
          <Timestamp value={task.ts} />
        </span>
        {onDelete && <TileDeleteButton onDelete={() => onDelete(task)} />}
      </div>
    </HoverCard>
  )
}
