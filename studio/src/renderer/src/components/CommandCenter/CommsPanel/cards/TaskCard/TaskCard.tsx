import { useState, useEffect } from 'react'
import { FileText, ChevronRight, ChevronDown, Pencil } from 'lucide-react'
import type { Message } from '../../../types'
import { Tooltip } from '../../../../ui'
import MarkdownRenderer from '../../../../shared/MarkdownRenderer/MarkdownRenderer'
import { RunPill } from '../../../../shared/RunPill/RunPill'
import { useElapsedProgress } from '../../../../shared/RunPill/progress'
import { CopyTextButton } from '../../../../shared/CopyTextButton/CopyTextButton'
import { useCommsStore } from '../../../../../store/commsStore'
import { TaskEditor } from './TaskEditor/TaskEditor'
import SendPreviewModal from '../../../../shared/SendPreviewModal/SendPreviewModal'
import { AbilityToggles } from '../../../../shared/AbilityToggles/AbilityToggles'
import type { Ability } from '../../../../../services/abilities'
import { headingLayers } from '../../../../../services/skillCompose'
import { useStore } from '../../../../../store'
import { useTaskRunPreview } from './useTaskRunPreview'
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

// A per-task build sends a large composed prompt (skill body + board context + task). Antigravity
// (agy) has no stdin / --prompt-file input, so that prompt overflows Windows' ~32KB command-line
// limit ("command line too long"). It's fine for the small editor actions (Split/Analyze/comments),
// so we disable it HERE only — not globally.
const TASK_UNAVAILABLE: Partial<Record<string, string>> = {
  antigravity: 'No headless large-prompt input (agy takes the prompt on the command line)',
}
const ADAPTER_OPTIONS = EDITOR_CLIS.map((c) => ({
  value: c.id,
  label: c.label,
  hint: TASK_UNAVAILABLE[c.id] ?? c.unavailable ?? c.hint,
  disabled: !!c.unavailable || !!TASK_UNAVAILABLE[c.id],
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
  const projectPath = useStore((st) => st.projectPath)
  const stopTask = useCommsStore((st) => st.stopTask)
  const editTaskText = useCommsStore((st) => st.editTaskText)
  const taskStart = useCommsStore((st) => st.taskRunStart[t.id])
  const progress = useElapsedProgress(taskStart || undefined)
  const ready = deps.every((d) => byId.get(d)?.taskStatus === 'done')
  const runnable = (status === 'pending' || status === 'failed') && ready
  const [justRan, setJustRan] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [abilities, setAbilities] = useState<Ability[]>([])
  const [editing, setEditing] = useState(false)
  useEffect(() => { if (status !== 'pending') setJustRan(false) }, [status])
  // Editing is offered for any task that isn't actively running — editing an in_progress task
  // (a live agent is building it) is the only real foot-gun. Editing a done/pending/failed/
  // blocked task is safe; the stored text is what a later run builds from, so edits take effect.
  const editable = status !== 'in_progress'
  const handleSaveEdit = (text: string): void => { editTaskText(t.id, text); setEditing(false) }
  // Preview-gated like the goal Run / Evaluate controls: the pill opens a confirm modal and
  // confirming dispatches. The backend builds from the STORED task text (by id), so the preview
  // is read-only — editing here wouldn't change what runs.
  const [adapter, setAdapter] = useState<EditorCli>(() => {
    const a = loadEditorCli(CLI_KEY_TASK)
    return TASK_UNAVAILABLE[a] ? 'claude' : a
  })
  const handleAdapter = (v: string): void => { setAdapter(v as EditorCli); saveEditorCli(CLI_KEY_TASK, v as EditorCli) }
  // The composed build prompt shown in the gate — a Sections trim is sent verbatim as
  // prompt_override; selected abilities compose into the build prompt either way.
  const preview = useTaskRunPreview(confirmOpen, t.text, abilities.map((a) => a.id))
  const handleRun = (): void => { setConfirmOpen(true) }
  const doRun = (finalPrompt?: string, sectionsUsed?: boolean): void => {
    setConfirmOpen(false)
    setJustRan(true)
    runTask(t.id, {
      adapter,
      abilityIds: abilities.length ? abilities.map((a) => a.id) : undefined,
      promptOverride: sectionsUsed ? finalPrompt : undefined,
    })
  }

  return (
    <>
    <div className={s.task} data-type="task" {...(expanded ? { 'data-expanded': 'true' } : {})}>
      <span
        className={s.dot}
        data-status={status}
        aria-label={`Task status: ${STATUS_LABEL[status]}`}
      />
      <div className={s.taskMain}>
        {editing ? (
          <TaskEditor initialText={t.text} onSave={handleSaveEdit} onCancel={() => setEditing(false)} />
        ) : (
          <>
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
              {editable && (
                <Tooltip label="Edit task text" placement="top">
                  <button type="button" className={s.editBtn} onClick={() => setEditing(true)} aria-label="Edit task text">
                    <Pencil size={12} />
                  </button>
                </Tooltip>
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
          </>
        )}
      </div>
    </div>
    {confirmOpen && (
      <SendPreviewModal
        title="Run task"
        engineLabel={cliLabel(adapter)}
        fileName={firstLine(t.text)}
        prompt={preview.prompt}
        readOnly
        headingLayers={headingLayers(preview.segments)}
        meta={[
          { label: 'Action', value: 'Build just this task' },
          { label: 'Skill', value: 'development/build' },
        ]}
        submitLabel="Run"
        footerSlot={
          <div className={s.gateControls}>
            <AbilityToggles projectRoot={projectPath} selectedIds={abilities.map((a) => a.id)} onChange={setAbilities} />
            <GoalSelect
              value={adapter}
              options={ADAPTER_OPTIONS}
              onChange={handleAdapter}
              ariaLabel="CLI engine"
              minWidth={110}
            />
          </div>
        }
        onSubmit={(finalPrompt, sectionsUsed) => doRun(finalPrompt, sectionsUsed)}
        onCancel={() => setConfirmOpen(false)}
      />
    )}
    </>
  )
}
