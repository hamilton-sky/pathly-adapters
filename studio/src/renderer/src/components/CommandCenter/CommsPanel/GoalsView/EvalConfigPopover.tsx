import { useEffect, useRef, useLayoutEffect } from 'react'
import { createPortal } from 'react-dom'
import { Target } from 'lucide-react'
import { type EditorCli } from '../.././../MarkdownEditor/EditorHeader/editorCli'
import { BoardSelect } from '../../../shared/BoardSelect/BoardSelect'
import type { DecomposeMode } from '../../../../store/commsApi'
import type { GoalStub } from './EvaluateBoardButton'
import { BoardEvalConfig } from './BoardEvalConfig/BoardEvalConfig'
import { GoalTargetConfig } from './GoalTargetConfig/GoalTargetConfig'
import s from './EvalConfigPopover.module.css'

// Max chars shown for a goal title in the Target dropdown.
const GOAL_LABEL_MAX = 42

interface Props {
  anchorEl: HTMLElement | null
  selectedLens: string
  lensText: string
  extraPrompt: string
  selectedCli: EditorCli
  running: boolean
  /** Goals on this board — populates the Target selector. */
  goals: GoalStub[]
  /** '' = whole board; otherwise = a goal id. */
  targetGoalId: string
  rigorMode: DecomposeMode
  onSelectLens: (name: string) => void
  onLensTextChange: (v: string) => void
  onExtraPromptChange: (v: string) => void
  onCliChange: (cli: EditorCli) => void
  onTargetChange: (goalId: string) => void
  onRigorChange: (mode: DecomposeMode) => void
  onReset: () => void
  onRun: () => void
  onClose: () => void
}

const POPOVER_WIDTH = 290

// Target options: "Whole board" first, then each goal (text truncated).
function buildTargetOptions(goals: GoalStub[]): { value: string; label: string; hint?: string }[] {
  return [
    { value: '', label: 'Whole board', hint: 'Evaluate everything and propose tasks' },
    ...goals.map((g) => ({
      value: g.id,
      label: g.text.length > GOAL_LABEL_MAX ? `${g.text.slice(0, GOAL_LABEL_MAX)}…` : g.text,
      hint: 'Decompose this goal into a task DAG',
    })),
  ]
}

// Portal shell + positioning for the evaluator config popover. Always shows the Target
// selector, then branches: whole board → BoardEvalConfig (lens/engine/preview); a specific
// goal → GoalTargetConfig (rigor/engine/Plan-now).
export function EvalConfigPopover({
  anchorEl, selectedLens, lensText, extraPrompt, selectedCli,
  running, goals, targetGoalId, rigorMode,
  onSelectLens, onLensTextChange, onExtraPromptChange, onCliChange,
  onTargetChange, onRigorChange, onReset, onRun, onClose,
}: Props): JSX.Element | null {
  const ref = useRef<HTMLDivElement>(null)
  const isGoalTarget = Boolean(targetGoalId)

  useLayoutEffect(() => {
    if (!anchorEl || !ref.current) return
    const r = anchorEl.getBoundingClientRect()
    let l = r.right - POPOVER_WIDTH
    if (l < 8) l = 8
    if (l + POPOVER_WIDTH > window.innerWidth - 8) l = window.innerWidth - 8 - POPOVER_WIDTH
    ref.current.style.setProperty('--pop-top', `${r.bottom + 6}px`)
    ref.current.style.setProperty('--pop-left', `${l}px`)
  }, [anchorEl])

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node
      if (t instanceof Element && t.closest('[data-board-select-menu]')) return
      if (ref.current && !ref.current.contains(t) && anchorEl && !anchorEl.contains(t)) onClose()
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [anchorEl, onClose])

  return createPortal(
    <div
      ref={ref}
      className={s.popover}
      role="dialog"
      aria-label="Configure evaluator"
    >
      {/* ── Target selector (always shown; locked while a dispatched run is live) ── */}
      <section className={s.section}>
        <label className={s.sectionLabel} htmlFor="eval-target">TARGET</label>
        <BoardSelect
          id="eval-target"
          ariaLabel="Evaluate target"
          value={targetGoalId}
          options={buildTargetOptions(goals)}
          onChange={(v) => onTargetChange(v)}
          leadingIcon={<Target size={13} />}
          disabled={running}
        />
      </section>

      {isGoalTarget ? (
        <GoalTargetConfig
          rigorMode={rigorMode}
          selectedCli={selectedCli}
          running={running}
          onRigorChange={onRigorChange}
          onCliChange={onCliChange}
          onRun={onRun}
        />
      ) : (
        <BoardEvalConfig
          selectedLens={selectedLens}
          lensText={lensText}
          extraPrompt={extraPrompt}
          selectedCli={selectedCli}
          running={running}
          onSelectLens={onSelectLens}
          onLensTextChange={onLensTextChange}
          onExtraPromptChange={onExtraPromptChange}
          onCliChange={onCliChange}
          onReset={onReset}
          onRun={onRun}
          onClose={onClose}
        />
      )}
    </div>,
    document.body,
  )
}
