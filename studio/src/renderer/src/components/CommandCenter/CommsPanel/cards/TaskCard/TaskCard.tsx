import { useState } from 'react'
import { FileText, ChevronRight, ChevronDown } from 'lucide-react'
import type { Message } from '../../../types'
import { Tooltip } from '../../../../ui'
import MarkdownRenderer from '../../../../shared/MarkdownRenderer/MarkdownRenderer'
import { RunPill } from '../../../../shared/RunPill/RunPill'
import { CopyTextButton } from '../../../../shared/CopyTextButton/CopyTextButton'
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

function firstLine(text: string): string {
  return text.split('\n').find((l) => l.trim()) ?? text
}

interface Props {
  task: Message
  siblings: Message[]
}

// A collapsible task banner: status dot + a one-line title + a copy icon + an expand chevron.
// Collapsed keeps the DAG list compact; expanded reveals the FULL task text in a scrolling box
// (a build task is a multi-line "what · Files · Done-when" block). The copy icon lifts the raw
// task text to the clipboard so a human can hand it to any agent.
export function TaskCard({ task: t, siblings }: Props): JSX.Element {
  const [expanded, setExpanded] = useState(false)
  const status: TaskStatus = t.taskStatus ?? 'pending'
  const byId = new Map(siblings.map((m) => [m.id, m]))
  const deps = t.dependsOn ?? []

  return (
    <div className={s.task} data-type="task" {...(expanded ? { 'data-expanded': 'true' } : {})}>
      <span
        className={s.dot}
        data-status={status}
        aria-label={`Task status: ${STATUS_LABEL[status]}`}
      />
      <div className={s.taskMain}>
        <div className={s.taskRow}>
          <Tooltip label={expanded ? 'Collapse task' : 'Expand task'} placement="top">
            <button
              type="button"
              className={s.banner}
              onClick={() => setExpanded((e) => !e)}
              {...(expanded ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
              aria-label={expanded ? 'Collapse task' : 'Expand task'}
            >
              <span className={s.chev}>
                {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              </span>
              <span className={s.bannerText}>{firstLine(t.text)}</span>
            </button>
          </Tooltip>
          {status === 'in_progress' && (
            <RunPill size="sm" state="running" idleLabel="In progress" disabled />
          )}
          <CopyTextButton text={t.text} label="task" />
        </div>
        {expanded && (
          <div className={s.taskFull}>
            <MarkdownRenderer content={t.text} />
          </div>
        )}
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
