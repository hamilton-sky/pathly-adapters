import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import s from './HoverCard.module.css'

interface Props {
  /** The rich preview shown on hover/focus. */
  card: ReactNode
  /** The trigger (a tile). */
  children: ReactNode
}

// Hover-intent delay: the mouse must rest on a tile this long before its preview
// opens, so cards don't flash while the cursor is just scanning across the grid.
const HOVER_DELAY_MS = 350

// A portal-positioned hover preview. Rendered to document.body and pinned to the
// trigger's rect, so it never gets clipped by the GridView scroll container. Opens
// on hover after a short intent delay, and immediately on keyboard focus (a
// deliberate landing, nothing to debounce); the preview itself is pointer-events:none.
export function HoverCard({ card, children }: Props): JSX.Element {
  const ref = useRef<HTMLDivElement>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [rect, setRect] = useState<DOMRect | null>(null)

  const open = (): void => {
    if (ref.current) setRect(ref.current.getBoundingClientRect())
  }
  const clearTimer = (): void => {
    if (timer.current) {
      clearTimeout(timer.current)
      timer.current = null
    }
  }
  // Mouse: wait out the intent delay before opening.
  const showDelayed = (): void => {
    clearTimer()
    timer.current = setTimeout(open, HOVER_DELAY_MS)
  }
  // Focus: open now — a keyboard user deliberately landed here.
  const showNow = (): void => {
    clearTimer()
    open()
  }
  // Leaving cancels any pending open, so a quick pass-over never fires a preview.
  const hide = (): void => {
    clearTimer()
    setRect(null)
  }

  // A pending timer must never outlive the component.
  useEffect(() => clearTimer, [])

  return (
    <div
      ref={ref}
      className={s.wrap}
      onMouseEnter={showDelayed}
      onMouseLeave={hide}
      onFocus={showNow}
      onBlur={hide}
    >
      {children}
      {rect
        ? createPortal(
            <div
              role="tooltip"
              className={s.card}
              style={{ left: rect.left, top: rect.top - 8, width: Math.max(rect.width, 240) }}
            >
              {card}
            </div>,
            document.body,
          )
        : null}
    </div>
  )
}
