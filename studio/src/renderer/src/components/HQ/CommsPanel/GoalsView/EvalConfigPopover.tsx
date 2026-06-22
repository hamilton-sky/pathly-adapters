import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import { createPortal } from 'react-dom'
import { Sparkles, ArrowRight } from 'lucide-react'
import CliSelect from '../.././../MarkdownEditor/EditorHeader/CliSelect/CliSelect'
import { type EditorCli } from '../.././../MarkdownEditor/EditorHeader/editorCli'
import { BoardSelect } from '../../../shared/BoardSelect/BoardSelect'
import { PromptBanner, usePromptContent } from '../../../shared/PromptPreview/PromptPreview'
import { useSkillCatalog } from '../../../Monitor/ConfigurePhaseModal/hooks/usePhaseModalCatalog'
import { useStore } from '../../../../store'
import { useUiStore } from '../../../../store/uiStore'
import { EVAL_LENSES } from '../SingleAgentButton/agentFormData'
import s from './EvalConfigPopover.module.css'

// The default "Propose tasks" lens runs the built-in evaluator, whose task body is
// this skill file — previewed (and opened) like an agent/skill, not edited inline.
const EVAL_SKILL_REL = 'planning/evaluate'

interface Props {
  anchorEl: HTMLElement | null
  /** Selected evaluation lens (EvalLens.name); '' = the default evaluator. */
  selectedLens: string
  /** The (possibly edited) lens prompt text used for the run. */
  lensText: string
  extraPrompt: string
  selectedCli: EditorCli
  running: boolean
  onSelectLens: (name: string) => void
  onLensTextChange: (v: string) => void
  onExtraPromptChange: (v: string) => void
  onCliChange: (cli: EditorCli) => void
  onReset: () => void
  onRun: () => void
  onClose: () => void
}

const POPOVER_WIDTH = 290

const LENS_OPTIONS = EVAL_LENSES.map((l) => ({ value: l.name, label: l.label, hint: l.hint }))

export function EvalConfigPopover({
  anchorEl, selectedLens, lensText, extraPrompt, selectedCli,
  running, onSelectLens, onLensTextChange, onExtraPromptChange, onCliChange,
  onReset, onRun, onClose,
}: Props): JSX.Element | null {
  const ref = useRef<HTMLDivElement>(null)
  const [top, setTop] = useState(0)
  const [left, setLeft] = useState(0)

  const projectPath = useStore((st) => st.projectPath)
  const setMdEditorPath = useUiStore((st) => st.setMdEditorPath)
  const setActivePanel = useUiStore((st) => st.setActivePanel)
  const skillCatalog = useSkillCatalog(projectPath)

  // A named lens ('') injects an inline, editable directive. The default lens runs
  // the built-in evaluator → preview its skill file (read-only) with an editor link.
  const lensPrompt = EVAL_LENSES.find((l) => l.name === selectedLens)?.prompt ?? ''
  const isDefaultLens = !lensPrompt

  const evaluateContent = usePromptContent(
    isDefaultLens ? EVAL_SKILL_REL : '',
    'src/pathly_data/core/skills', skillCatalog,
    { [EVAL_SKILL_REL]: EVAL_SKILL_REL }, {}, projectPath,
  )
  const evaluateMdPath = projectPath ? `${projectPath}/src/pathly_data/core/skills/${EVAL_SKILL_REL}.md` : null

  function openEvaluateSkill(): void {
    if (!evaluateMdPath) return
    setMdEditorPath(evaluateMdPath)
    setActivePanel('markdown-editor')
    onClose()
  }

  // Position below the anchor, right-aligned.
  useLayoutEffect(() => {
    if (!anchorEl) return
    const r = anchorEl.getBoundingClientRect()
    let l = r.right - POPOVER_WIDTH
    if (l < 8) l = 8
    if (l + POPOVER_WIDTH > window.innerWidth - 8) l = window.innerWidth - 8 - POPOVER_WIDTH
    setTop(r.bottom + 6)
    setLeft(l)
  }, [anchorEl])

  // Outside-click and Escape close.
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node
      // The lens dropdown portals its menu outside this popover — clicks there must
      // not be read as "outside" or selecting a lens would close the whole popover.
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
      style={{ '--pop-top': `${top}px`, '--pop-left': `${left}px` } as React.CSSProperties}
      role="dialog"
      aria-label="Configure evaluator"
    >
      <div className={s.heading}>Configure evaluator</div>

      {/* Lens — shapes HOW the board is read (not which worker runs). */}
      <section className={s.section}>
        <label className={s.sectionLabel} htmlFor="eval-lens">LENS</label>
        <BoardSelect
          id="eval-lens"
          ariaLabel="Evaluation lens"
          value={selectedLens}
          options={LENS_OPTIONS}
          onChange={onSelectLens}
          leadingIcon={<Sparkles size={13} />}
        />
        {isDefaultLens ? (
          <PromptBanner
            content={evaluateContent}
            mdEditorPath={evaluateMdPath}
            onOpenMdEditor={openEvaluateSkill}
          />
        ) : (
          <PromptBanner editable editValue={lensText} onEditChange={onLensTextChange} />
        )}
      </section>

      {/* Extra instructions */}
      <section className={s.section}>
        <label className={s.sectionLabel} htmlFor="eval-extra">EXTRA INSTRUCTIONS <span className={s.optional}>· optional</span></label>
        <textarea
          id="eval-extra"
          className={s.textarea}
          rows={3}
          placeholder="Any extra context or instructions for this run…"
          value={extraPrompt}
          onChange={(e) => onExtraPromptChange(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); onRun() }
          }}
        />
      </section>

      {/* Engine */}
      <section className={s.section}>
        <span className={s.sectionLabel}>ENGINE</span>
        <CliSelect value={selectedCli} onChange={onCliChange} align="right" up />
      </section>

      {/* Redirect — agents & skills live in the full run modal, not here. */}
      <div className={s.redirect}>
        <ArrowRight size={12} className={s.redirectIcon} />
        Need an agent or skill? Use <strong>Run on this board</strong>
      </div>

      <footer className={s.footer}>
        <button type="button" className={s.resetBtn} onClick={onReset}>Reset</button>
        <span className={s.spacer} />
        <button type="button" className={s.runBtn} disabled={running} onClick={onRun}>
          Run now
        </button>
      </footer>
    </div>,
    document.body,
  )
}
