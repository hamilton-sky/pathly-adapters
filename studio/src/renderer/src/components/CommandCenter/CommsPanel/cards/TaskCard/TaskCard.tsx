import { FileText } from 'lucide-react'
import type { Message } from '../../../types'
import MarkdownRenderer from '../../../../shared/MarkdownRenderer/MarkdownRenderer'
import { RunPill } from '../../../../shared/RunPill/RunPill'
import s from './TaskCard.module.css'

type TaskStatus = NonNullable<Message['taskStatus']>

const STATUS_LABEL: Record<TaskStatus, string> = {
  pending: 'pending',
  in_progress: 'in progress',
  done: 'done',
  blocked: 'blocked',
  failed: 'failed',
}

function basename(path: string): string {
  return path.split(/[/\\]/).pop() ?? path
}

interface Props {
  task: Message
  siblings: Message[]
}

// A single task row: status dot + text + (optional) artifact label + dependency badges.
// (A per-task ad-hoc "Run task" button is a future affordance — no backend route yet.)
export function TaskCard({ task: t, siblings }: Props): JSX.Element {
  const status: TaskStatus = t.taskStatus ?? 'pending'
  const byId = new Map(siblings.map((m) => [m.id, m]))
  const deps = t.dependsOn ?? []

  return (
    <div className={s.task} data-type="task">
      <span
        className={s.dot}
        data-status={status}
        aria-label={`Task status: ${STATUS_LABEL[status]}`}
      />
      <div className={s.taskMain}>
        <div className={s.taskRow}>
          <div className={s.taskText} title={t.text}>
            <MarkdownRenderer content={t.text} className={s.taskMd} />
          </div>
          {status === 'in_progress' && (
            <RunPill size="sm" state="running" idleLabel="In progress" disabled />
          )}
        </div>
        {t.artifactPath && (
          <div className={s.taskArtifact}>
            <FileText size={11} />
            <span className={s.artName}>{basename(t.artifactPath)}</span>
          </div>
        )}
        {deps.length > 0 && (
          <div className={s.deps} aria-label="Dependencies">
            {deps.map((d) => {
              const depStatus = byId.get(d)?.taskStatus ?? 'pending'
              return (
                <span key={d} className={s.depBadge} data-status={depStatus}>
                  dep
                </span>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
