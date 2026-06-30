// Boxed "Add to board" target picker — a small square popover (portaled to <body>): the broad
// scopes (Global / Project) sit in a top row, the feature boards in a scrollable list below.
// The path-derived target is marked "suggested". Closes on outside-click / Escape / scroll.

import React, { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Check, Globe, FolderGit2, GitBranch } from 'lucide-react'
import type { BoardTarget, BoardTargetOption } from './AddToBoardButton'
import s from './BoardTargetMenu.module.css'

interface Props {
  targets: BoardTargetOption[]
  position: { x: number; y: number }
  onPick: (t: BoardTarget) => void
  onClose: () => void
}

export default function BoardTargetMenu({ targets, position, onPick, onClose }: Props): JSX.Element {
  const ref = useRef<HTMLDivElement>(null)

  // Position via CSS custom properties (no inline style prop) — set imperatively after mount.
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.setProperty('--menu-top', `${position.y}px`)
    el.style.setProperty('--menu-left', `${position.x}px`)
  }, [position])

  useEffect(() => {
    function onDown(e: MouseEvent): void {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    function onKey(e: KeyboardEvent): void {
      if (e.key === 'Escape') onClose()
    }
    function onShift(e: Event): void {
      // Scrolling within the menu's own list must not dismiss it.
      if (e.type === 'scroll' && ref.current && ref.current.contains(e.target as Node)) return
      onClose()
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    window.addEventListener('resize', onShift)
    window.addEventListener('scroll', onShift, true)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
      window.removeEventListener('resize', onShift)
      window.removeEventListener('scroll', onShift, true)
    }
  }, [onClose])

  const scopes = targets.filter((o) => o.target.board !== 'feature')
  const features = targets.filter((o) => o.target.board === 'feature')

  function pick(o: BoardTargetOption): void {
    onClose()
    onPick(o.target)
  }

  return createPortal(
    <div ref={ref} className={s.menu} role="menu" aria-label="Add to board">
      <div className={s.title}>Add to board</div>
      <div className={s.scopes}>
        {scopes.map((o) => (
          <button
            key={o.key}
            type="button"
            role="menuitem"
            className={s.scopeBtn}
            data-suggested={o.suggested ? 'true' : 'false'}
            onClick={() => pick(o)}
          >
            {o.target.board === 'global' ? <Globe size={13} /> : <FolderGit2 size={13} />}
            <span className={s.scopeLabel}>{o.label}</span>
            {o.suggested && <Check size={12} className={s.sugg} />}
          </button>
        ))}
      </div>
      {features.length > 0 && (
        <>
          <div className={s.label}>Feature boards</div>
          <div className={s.scroll}>
            {features.map((o) => (
              <button
                key={o.key}
                type="button"
                role="menuitem"
                className={s.item}
                data-suggested={o.suggested ? 'true' : 'false'}
                onClick={() => pick(o)}
              >
                <GitBranch size={12} className={s.itemIcon} />
                <span className={s.itemLabel}>{o.label}</span>
                {o.suggested && <span className={s.tag}>suggested</span>}
              </button>
            ))}
          </div>
        </>
      )}
    </div>,
    document.body,
  )
}
