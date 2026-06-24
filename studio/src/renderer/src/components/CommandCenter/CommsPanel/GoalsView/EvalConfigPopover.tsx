import { useEffect, useRef, useLayoutEffect } from 'react'
import { createPortal } from 'react-dom'
import { ArrowRight } from 'lucide-react'
import { type EditorCli } from '../.././../MarkdownEditor/EditorHeader/editorCli'
import { PromptBanner, usePromptContent } from '../../../shared/PromptPreview/PromptPreview'
import { PromptActionConfig } from '../../../shared/PromptActionConfig/PromptActionConfig'
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

export function EvalConfigPopover({
  anchorEl, selectedLens, lensText, extraPrompt, selectedCli,
  running, onSelectLens, onLensTextChange, onExtraPromptChange, onCliChange,
  onReset, onRun, onClose,
}: Props): JSX.Element | null {
  const ref = useRef<HTMLDivElement>(null)

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
    if (!anchorEl || !ref.current) return
    const r = anchorEl.getBoundingClientRect()
    let l = r.right - POPOVER_WIDTH
    if (l < 8) l = 8
    if (l + POPOVER_WIDTH > window.innerWidth - 8) l = window.innerWidth - 8 - POPOVER_WIDTH
    ref.current.style.setProperty('--pop-top', `${r.bottom + 6}px`)
    ref.current.style.setProperty('--pop-left', `${l}px`)
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

  const footerNote = (
    <>
      <ArrowRight size={12} className={s.redirectIcon} />
      Need an agent or skill? Use <strong>Run on this board</strong>
    </>
  )

  const bannerSlot = isDefaultLens ? (
    <PromptBanner
      content={evaluateContent}
      mdEditorPath={evaluateMdPath}
      onOpenMdEditor={openEvaluateSkill}
    />
  ) : undefined

  return createPortal(
    <div
      ref={ref}
      className={s.popover}
      role="dialog"
      aria-label="Configure evaluator"
    >
      <PromptActionConfig
        heading="Configure evaluator"
        presetLabel="LENS"
        presets={EVAL_LENSES}
        selectedPreset={selectedLens}
        promptText={lensText}
        extra={extraPrompt}
        cli={selectedCli}
        running={running}
        primaryLabel="Run now"
        onSelectPreset={onSelectLens}
        onPromptTextChange={onLensTextChange}
        onExtraChange={onExtraPromptChange}
        onCliChange={onCliChange}
        onReset={onReset}
        onPrimary={onRun}
        bannerSlot={bannerSlot}
        footerNote={footerNote}
      />
    </div>,
    document.body,
  )
}
