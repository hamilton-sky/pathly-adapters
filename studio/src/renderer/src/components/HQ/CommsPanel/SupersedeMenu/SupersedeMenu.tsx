import React, { useState } from 'react'
import { MoreVertical } from 'lucide-react'
import type { Message } from '../../../CommandCenter/types'
import s from './SupersedeMenu.module.css'

export function SupersedeMenu(
  { message, candidates, onSupersede }:
  { message: Message; candidates: Message[]; onSupersede: (oldId: string, newId: string) => void },
) {
  const [open, setOpen] = useState(false)
  // Only a NEWER message of the same type can supersede this one. ISO timestamps
  // compare lexicographically; if either ts is missing, fall back to allowing it.
  const newer = candidates.filter(
    (c) =>
      c.id !== message.id &&
      c.type === message.type &&
      (!c.ts || !message.ts || c.ts > message.ts),
  )
  return (
    <div className={s.wrap}>
      <button
        type="button"
        className={s.btn}
        aria-label="Message actions"
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        onClick={() => setOpen((o) => !o)}
      >
        <MoreVertical size={12} />
      </button>
      {open && (
        <div className={s.menu} role="menu">
          <div className={s.menuHead}>Supersede with…</div>
          {newer.length === 0 && <div className={s.empty}>No newer message</div>}
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
