import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, Network, ListTree, Target, Rows3, Columns3, LayoutGrid, RotateCcw } from 'lucide-react'
import type { Message } from '../../types'
import { useFocusTrap } from '../../../../hooks/useFocusTrap'
import { Tooltip } from '../../../ui'
import MarkdownRenderer from '../../../shared/MarkdownRenderer/MarkdownRenderer'
import { CopyTextButton } from '../../../shared/CopyTextButton/CopyTextButton'
import { BoardSelect } from '../../../shared/BoardSelect/BoardSelect'
import { TaskCard } from '../cards/TaskCard/TaskCard'
import { TaskDagView } from './TaskDagView/TaskDagView'
import type { DagOrient } from './TaskDagView/dagLayout'
import { orderByDeps, computeRollup, serializeTasks } from '../GoalsView/goalsViewUtils'
import s from './GoalDetailModal.module.css'

interface Props {
  messages: Message[]
  initialGoalId: string
  onClose: () => void
}

type Tab = 'dag' | 'overview'
const ALL = '__all__'

function firstLine(text: string): string {
  return text.split('\n').find((l) => l.trim()) ?? text
}

// Full goal+tasks modal. A single compact top bar carries: tabs (DAG / Tasks), the DAG layout
// controls (top-down / left-right / snake + auto-arrange), the task rollup, a compact goal selector
// (incl. an All-goals cross-goal view), and close. Mirrors ArtifactModal's portal + focus-trap shell.
export function GoalDetailModal({ messages, initialGoalId, onClose }: Props): JSX.Element {
  const boxRef = useRef<HTMLDivElement>(null)
  useFocusTrap(boxRef)
  const [tab, setTab] = useState<Tab>('dag')
  const [goalId, setGoalId] = useState<string>(initialGoalId)
  const [orient, setOrient] = useState<DagOrient>('vertical')
  const [dagKey, setDagKey] = useState(0) // bump to remount TaskDagView → auto-arrange (clear drags + view)

  const goals = useMemo(() => messages.filter((m) => m.type === 'goal'), [messages])
  const isAll = goalId === ALL
  const goal = goals.find((g) => g.id === goalId) ?? null
  const tasks = useMemo(
    () => messages.filter((m) => m.type === 'task' && (isAll || m.goal_id === goalId)),
    [messages, goalId, isAll],
  )
  const ordered = useMemo(() => orderByDeps(tasks), [tasks])
  const r = computeRollup(tasks)
  const headerText = isAll ? 'All goals' : goal?.text ?? 'Goal'

  useEffect(() => {
    function onKey(e: KeyboardEvent): void {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const LAYOUTS: { value: DagOrient; icon: JSX.Element; label: string }[] = [
    { value: 'vertical', icon: <Rows3 size={13} />, label: 'Top-down tree' },
    { value: 'horizontal', icon: <Columns3 size={13} />, label: 'Left-right tree' },
    { value: 'snake', icon: <LayoutGrid size={13} />, label: 'Snake (compact grid)' },
  ]

  return createPortal(
    <div className={s.backdrop} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div ref={boxRef} role="dialog" aria-modal="true" aria-label="Goal details" className={s.modal}>
        <div className={s.topbar}>
          <div className={s.tabs} role="tablist">
            <button type="button" role="tab" className={s.tab} data-active={tab === 'dag' ? 'true' : 'false'} {...(tab === 'dag' ? { 'aria-selected': 'true' } : { 'aria-selected': 'false' })} onClick={() => setTab('dag')}>
              <Network size={13} /> DAG
            </button>
            <button type="button" role="tab" className={s.tab} data-active={tab === 'overview' ? 'true' : 'false'} {...(tab === 'overview' ? { 'aria-selected': 'true' } : { 'aria-selected': 'false' })} onClick={() => setTab('overview')}>
              <ListTree size={13} /> Tasks
            </button>
          </div>

          {tab === 'dag' && (
            <div className={s.dagCtl}>
              <div className={s.seg} role="group" aria-label="Layout direction">
                {LAYOUTS.map((l) => (
                  <Tooltip key={l.value} label={l.label} placement="bottom">
                    <button type="button" className={s.segBtn} data-active={orient === l.value ? 'true' : 'false'} onClick={() => setOrient(l.value)} aria-label={l.label}>
                      {l.icon}
                    </button>
                  </Tooltip>
                ))}
              </div>
              <Tooltip label="Auto-arrange" placement="bottom">
                <button type="button" className={s.iconBtn} onClick={() => setDagKey((k) => k + 1)} aria-label="Auto-arrange"><RotateCcw size={13} /></button>
              </Tooltip>
            </div>
          )}

          <span className={s.spacer} />
          <BoardSelect
            value={goalId}
            onChange={setGoalId}
            ariaLabel="Select goal"
            leadingIcon={<Target size={14} />}
            triggerClassName={s.goalSelect}
            options={[
              { value: ALL, label: `All goals (${goals.length})` },
              ...goals.map((g) => ({ value: g.id, label: firstLine(g.text) })),
            ]}
          />
          <button type="button" className={s.close} onClick={onClose} aria-label="Close"><X size={15} /></button>
        </div>

        <div className={s.body}>
          {tab === 'dag' ? (
            <TaskDagView key={dagKey} tasks={tasks} order={ordered} orient={orient} />
          ) : (
            <div className={s.overview}>
              {!isAll && goal?.text && (
                <div className={s.goalText}>
                  <MarkdownRenderer content={goal.text} />
                </div>
              )}
              <div className={s.taskList}>
                {ordered.length > 0
                  ? ordered.map((t) => <TaskCard key={t.id} task={t} siblings={messages} />)
                  : <div className={s.noTasks}>No tasks decomposed yet.</div>}
              </div>
            </div>
          )}
        </div>

        <footer className={s.foot}>
          <div className={s.footSide}>
            {tasks.length > 0 && (
              <CopyTextButton text={serializeTasks(headerText, tasks)} label="all tasks" />
            )}
          </div>
          <span className={s.rollup}>
            {r.total} task{r.total !== 1 ? 's' : ''} · {r.done} done · {r.ready} ready
            {r.failed > 0 ? ` · ${r.failed} blocked` : ''}
          </span>
          <button type="button" className={s.btnQuiet} onClick={onClose}>Close</button>
        </footer>
      </div>
    </div>,
    document.body,
  )
}
