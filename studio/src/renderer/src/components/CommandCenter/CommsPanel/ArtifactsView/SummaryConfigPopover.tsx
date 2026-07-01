import { useEffect, useLayoutEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { type AiSelection } from '../../../../services/aiRouter'
import type { SummaryStyle } from '../../../../store/commsApi'
import { SummaryConfigBody } from '../SummaryConfigBody/SummaryConfigBody'
import s from './SummaryConfigPopover.module.css'

interface Props {
  anchorEl: HTMLElement | null
  selection: AiSelection | null
  onSelectionChange: (sel: AiSelection) => void
  style: SummaryStyle
  onStyleChange: (style: SummaryStyle) => void
  /** Per-board default instruction, appended to every dropped artifact's summary. */
  note: string
  onNoteChange: (note: string) => void
  onClose: () => void
}

const POPOVER_WIDTH = 320

// Portal popover for the board-level summary config (defaults for artifacts dropped
// on this board). Anchored under its trigger, right-aligned; closes on outside-click
// or Escape. Renders the shared SummaryConfigBody so it matches the per-artifact
// popover exactly. Positioning mirrors EvalConfigPopover (--pop-top/--pop-left).
export function SummaryConfigPopover({
  anchorEl, selection, onSelectionChange, style, onStyleChange, note, onNoteChange, onClose,
}: Props): JSX.Element | null {
  const ref = useRef<HTMLDivElement>(null)

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
    <div ref={ref} className={s.popover} role="dialog" aria-label="Summary settings">
      <SummaryConfigBody
        style={style}
        onStyleChange={onStyleChange}
        selection={selection}
        onSelectionChange={onSelectionChange}
        note={note}
        onNoteChange={onNoteChange}
        targetLabel="AI target"
        noteLabel="Default instruction for this board"
        notePlaceholder="e.g. always focus on security; write for a non-technical reader"
      />
    </div>,
    document.body,
  )
}
