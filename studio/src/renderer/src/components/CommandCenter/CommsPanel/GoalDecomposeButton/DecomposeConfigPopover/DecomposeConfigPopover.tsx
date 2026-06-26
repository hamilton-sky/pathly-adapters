import { useEffect, useRef, useLayoutEffect } from 'react'
import { createPortal } from 'react-dom'
import { Boxes } from 'lucide-react'
import { BoardSelect } from '../../../../shared/BoardSelect/BoardSelect'
import CliSelect from '../../../../MarkdownEditor/EditorHeader/CliSelect/CliSelect'
import { type EditorCli } from '../../../../MarkdownEditor/EditorHeader/editorCli'
import type { DecomposeMode } from '../../../../../store/commsApi'
import s from './DecomposeConfigPopover.module.css'

// Mode picker hints (mirror the old BoardSelect dropdown): fast/shallow vs deep/full-team.
export const MODE_OPTIONS = [
  { value: 'planner', label: 'Planner', hint: 'Fast · DAG only' },
  { value: 'consultation', label: 'Consultation', hint: 'Deep · full team' },
]

interface Props {
  anchorEl: HTMLElement | null
  mode: DecomposeMode
  selectedCli: EditorCli
  onModeChange: (mode: DecomposeMode) => void
  onCliChange: (cli: EditorCli) => void
  onRun: () => void
  onClose: () => void
}

const POPOVER_WIDTH = 260

// Gear-anchored popover for the Decompose control — mirrors EvalConfigPopover: a mode
// picker (planner / consultation) + the SAME CLI-engine picker (CliSelect) the evaluator
// uses, plus a "Run now" primary. Positioned below the gear, right-aligned, with
// outside-click / Escape close.
export function DecomposeConfigPopover({
  anchorEl, mode, selectedCli, onModeChange, onCliChange, onRun, onClose,
}: Props): JSX.Element | null {
  const ref = useRef<HTMLDivElement>(null)

  // Position below the anchor, right-aligned (clamped to the viewport).
  useLayoutEffect(() => {
    if (!anchorEl || !ref.current) return
    const r = anchorEl.getBoundingClientRect()
    let l = r.right - POPOVER_WIDTH
    if (l < 8) l = 8
    if (l + POPOVER_WIDTH > window.innerWidth - 8) l = window.innerWidth - 8 - POPOVER_WIDTH
    ref.current.style.setProperty('--pop-top', `${r.bottom + 6}px`)
    ref.current.style.setProperty('--pop-left', `${l}px`)
  }, [anchorEl])

  // Outside-click and Escape close. The mode dropdown portals its menu outside this
  // popover, so clicks inside it must not be read as "outside" (mirrors EvalConfigPopover).
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
    <div ref={ref} className={s.popover} role="dialog" aria-label="Configure decompose">
      <div className={s.heading}>Configure decompose</div>

      <section className={s.section}>
        <label className={s.sectionLabel} htmlFor="dec-mode">MODE</label>
        <BoardSelect
          id="dec-mode"
          ariaLabel="Decompose mode"
          value={mode}
          options={MODE_OPTIONS}
          onChange={(v) => onModeChange(v as DecomposeMode)}
          leadingIcon={<Boxes size={13} />}
        />
      </section>

      <section className={s.section}>
        <span className={s.sectionLabel}>ENGINE</span>
        <CliSelect value={selectedCli} onChange={onCliChange} align="right" up />
      </section>

      <div className={s.footer}>
        <button type="button" className={s.runBtn} onClick={onRun}>Run now</button>
      </div>
    </div>,
    document.body,
  )
}
