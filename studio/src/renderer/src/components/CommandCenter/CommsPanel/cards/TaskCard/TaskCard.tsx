import { useState, useEffect } from 'react'
import { FileText, ChevronRight, ChevronDown } from 'lucide-react'
import type { Message } from '../../../types'
import { Tooltip } from '../../../../ui'
import MarkdownRenderer from '../../../../shared/MarkdownRenderer/MarkdownRenderer'
import { RunPill } from '../../../../shared/RunPill/RunPill'
import { useElapsedProgress } from '../../../../shared/RunPill/progress'
import { CopyTextButton } from '../../../../shared/CopyTextButton/CopyTextButton'
import { useCommsStore } from '../../../../../store/commsStore'
import SendPreviewModal from '../../../../shared/SendPreviewModal/SendPreviewModal'
import { GoalSelect } from '../../GoalRunButton/GoalSelect/GoalSelect'
import {
  type EditorCli,
  loadEditorCli,
  saveEditorCli,
  cliLabel,
  CLI_KEY_TASK,
  EDITOR_CLIS,
} from '../../../../MarkdownEditor/EditorHeader/editorCli'
import s from './TaskCard.module.css'

const ADAPTER_OPTIONS = EDITOR_CLIS.map((c) => ({
  value: c.id,
  label: c.label,
  hint: c.unavailable ?? c.hint,
  disabled: !!c.unavailable,
}))

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

  // Per-task run: only runnable when pending/failed AND every dependency is done. The backend
  // claims the task (→ in_progress) and completes it, so the task's own status drives the pill;
  // `justRan` is a brief optimistic flag until that status catches up (and prevents double-fire).
  const runTask = useCommsStore((st) => st.runTask)
  const stopTask = useCommsStore((st) => st.stopTask)
  const taskStart = useCommsStore((st) => st.taskRunStart[t.id])
  const progress = useElapsedProgress(taskStart || undefined)
  const ready = deps.every((d) => byId.get(d)?.taskStatus === 'done')
  const runnable = (status === 'pending' || status === 'failed') && ready
  const [justRan, setJustRan] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  useEffect(() => { if (status !== 'pending') setJustRan(false) }, [status])
  // Preview-gated like the goal Run / Evaluate controls: the pill opens a confirm modal and
  // confirming dispatches. The backend builds from the STORED task text (by id), so the preview
  // is read-only — editing here wouldn't change what runs.
  const [adapter, setAdapter] = useState<EditorCli>(() => loadEditorCli(CLI_KEY_TASK))
  const handleAdapter = (v: string): void => { setAdapter(v as EditorCli); saveEditorCli(CLI_KEY_TASK, v as EditorCli) }
  const handleRun = (): void => { setConfirmOpen(true) }
  const doRun = (): void => { setConfirmOpen(false); setJustRan(true); runTask(t.id, { adapter }) }

  return (
    <>
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
          {status === 'in_progress' || justRan ? (
            <RunPill size="sm" state="running" idleLabel="In progress" progress={progress} onStop={() => stopTask(t.id)} />
          ) : runnable ? (
            <Tooltip label="Build just this task" placement="top">
              <RunPill size="sm" state="idle" idleLabel="Run" onRun={handleRun} />
            </Tooltip>
          ) : null}
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
    {confirmOpen && (
      <SendPreviewModal
        title="Run task"
        engineLabel={cliLabel(adapter)}
        fileName={firstLine(t.text)}
        prompt={t.text}
        readOnly
        meta={[
          { label: 'Action', value: 'Build just this task' },
          { label: 'Skill', value: 'development/build' },
        ]}
        submitLabel="Run"
        footerSlot={
          <GoalSelect
            value={adapter}
            options={ADAPTER_OPTIONS}
            onChange={handleAdapter}
            ariaLabel="CLI engine"
            minWidth={110}
          />
        }
        onSubmit={doRun}
        onCancel={() => setConfirmOpen(false)}
      />
    )}
    </>
  )
}
