import React, { useEffect, useRef, useState } from 'react'
import { MoreVertical } from 'lucide-react'
import type { Message } from '../../../CommandCenter/types'
import s from './SupersedeMenu.module.css'

export function SupersedeMenu(
  { message, candidates, onSupersede }:
  { message: Message; candidates: Message[]; onSupersede: (oldId: string, newId: string) => void },
) {
  const [open, setOpen] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  // Close on outside click or Escape.
  useEffect(() => {
    if (!open) return
    function onDown(e: MouseEvent): void {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent): void { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  // Only a NEWER message of the same type can supersede this one. ISO timestamps
  // compare lexicographically; if either ts is missing, fall back to allowing it.
  const newer = candidates.filter(
    (c) =>
      c.id !== message.id &&
      c.type === message.type &&
      (!c.ts || !message.ts || c.ts > message.ts),
  )

  // Nothing to supersede with → don't show the control at all (no dead-end menu).
  if (newer.length === 0) return null

  return (
    <div className={s.wrap} ref={wrapRef}>
      <button
        type="button"
        className={s.btn}
        aria-label="Supersede this message"
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        onClick={() => setOpen((o) => !o)}
      >
        <MoreVertical size={12} />
      </button>
      {open && (
        <div className={s.menu} role="menu">
          <div className={s.menuHead}>Supersede with…</div>
          {newer.map((c) => (
            <button
              key={c.id}
              type="button"
              role="menuitem"
              className={s.item}
              onClick={() => { onSupersede(message.id, c.id); setOpen(false) }}
            >
              {c.text.slice(0, 60)}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
