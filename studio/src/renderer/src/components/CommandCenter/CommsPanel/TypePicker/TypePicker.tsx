import React, { useState, useEffect, useRef } from 'react'
import { ChevronDown, Check } from 'lucide-react'
import type { MessageType } from '../../types'
import { COMPOSE_TYPES } from '../../constants'
import s from './TypePicker.module.css'

// Custom message-type dropdown that opens UPWARD (the compose bar sits at the
// bottom of the panel). Replaces a native <select> to control drop direction
// and avoid the chevron-repaint flicker on hover.
export function TypePicker({ value, onChange }: { value: MessageType; onChange: (t: MessageType) => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  return (
    <div className={s.wrap} ref={ref}>
      <button
        type="button"
        className={s.trigger}
        title="Message type"
        aria-haspopup="listbox"
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        onClick={() => setOpen((o) => !o)}
      >
        {value}
        <ChevronDown size={12} className={s.chev} />
      </button>

      {open && (
        <div className={s.menu} role="listbox">
          {COMPOSE_TYPES.map((t) => (
            <button
              key={t}
              type="button"
              role="option"
              aria-selected={t === value}
              className={s.item}
              {...(t === value ? { 'data-active': '' } : {})}
              onClick={() => { onChange(t); setOpen(false) }}
            >
              <span className={s.check}>{t === value && <Check size={12} />}</span>
              {t}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
