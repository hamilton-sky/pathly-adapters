import { useEffect, useRef, useLayoutEffect } from 'react'
import { createPortal } from 'react-dom'
import type { AiSelection } from '../../../../../../../services/aiRouter'
import type { SummaryStyle } from '../../../../../../../store/commsApi'
import { SummaryConfigBody } from '../../../../SummaryConfigBody/SummaryConfigBody'
import s from './SummaryTargetPopover.module.css'

interface Props {
  anchorEl: HTMLButtonElement | null
  value: AiSelection
  onChange: (sel: AiSelection) => void
  style: SummaryStyle
  onStyleChange: (style: SummaryStyle) => void
  note: string
  onNoteChange: (note: string) => void
  onClose: () => void
}

const POPOVER_WIDTH = 320

// Gear-anchored popover for the per-artifact summary config. Portals to body,
// positioned relative to the gear button (above or below depending on viewport
// space). Outside-click + Escape to close. The inner sections come from the shared
// SummaryConfigBody so this and the board-level SummaryConfig stay identical.
export function SummaryTargetPopover({ anchorEl, value, onChange, style, onStyleChange, note, onNoteChange, onClose }: Props): JSX.Element | null {
  const ref = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    if (!anchorEl || !ref.current) return
    const r = anchorEl.getBoundingClientRect()
    const popH = ref.current.offsetHeight || 100
    let l = r.right - POPOVER_WIDTH
    if (l < 8) l = 8
    if (l + POPOVER_WIDTH > window.innerWidth - 8) l = window.innerWidth - 8 - POPOVER_WIDTH
    // Prefer above the anchor (card footers may be near the bottom), fall back below.
    const topAbove = r.top - popH - 6
    const top = topAbove >= 8 ? topAbove : r.bottom + 6
    ref.current.style.setProperty('--pop-top', `${top}px`)
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
    <div ref={ref} className={s.popover} role="dialog" aria-label="Choose AI target and summary depth">
      <SummaryConfigBody
        style={style}
        onStyleChange={onStyleChange}
        selection={value}
        onSelectionChange={onChange}
        note={note}
        onNoteChange={onNoteChange}
        targetLabel="AI target for this artifact"
        noteLabel="Special request (optional)"
        notePlaceholder="e.g. focus on the security parts; write for a non-technical reader"
      />
    </div>,
    document.body,
  )
}
