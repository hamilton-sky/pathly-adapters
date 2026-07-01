import { useEffect, useLayoutEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Check } from 'lucide-react'
import type { MessageType } from '../../types'
import { MessageTypeBadge } from '../MessageTypeBadge/MessageTypeBadge'
import { FILTER_GROUPS } from './filterTypes'
import s from './FilterPopover.module.css'

interface Props {
  anchorEl: HTMLElement | null
  value: MessageType[]
  onChange: (types: MessageType[]) => void
  onClose: () => void
}

const POPOVER_WIDTH = 268

// Portal popover of message-type chips, grouped by role (Conversation / Knowledge /
// Status / Signals) and multi-select. Chips stay full-opacity so low-contrast types
// (e.g. status) are legible; the selected state is an accent ring + check, not a
// dim/bright swap. Toggling a chip adds/removes its type; empty = show all. Anchored
// under its trigger, closes on outside-click or Escape.
export function FilterPopover({ anchorEl, value, onChange, onClose }: Props): JSX.Element | null {
  const ref = useRef<HTMLDivElement>(null)
  const selected = new Set(value)

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

  function toggle(t: MessageType): void {
    const next = new Set(selected)
    if (next.has(t)) next.delete(t)
    else next.add(t)
    onChange([...next])
  }

  return createPortal(
    <div ref={ref} className={s.popover} role="dialog" aria-label="Filter by type">
      <div className={s.head}>
        <span className={s.title}>Filter by type</span>
        {value.length > 0 && (
          <button type="button" className={s.clear} onClick={() => onChange([])}>Clear</button>
        )}
      </div>
      <div className={s.groups}>
        {FILTER_GROUPS.map((g) => (
          <div key={g.label} className={s.group}>
            <div className={s.groupLabel}>{g.label}</div>
            <div className={s.chips}>
              {g.types.map((t) => {
                const on = selected.has(t)
                return (
                  <button
                    key={t}
                    type="button"
                    className={s.chip}
                    {...(on ? { 'data-on': '' } : {})}
                    {...(on ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
                    onClick={() => toggle(t)}
                  >
                    <span className={s.checkSlot}>{on && <Check size={11} />}</span>
                    <MessageTypeBadge type={t} />
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>,
    document.body,
  )
}
