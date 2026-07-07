import { useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import s from './HoverCard.module.css'

interface Props {
  /** The rich preview shown on hover/focus. */
  card: ReactNode
  /** The trigger (a tile). */
  children: ReactNode
}

// A portal-positioned hover preview. Rendered to document.body and pinned to the
// trigger's rect, so it never gets clipped by the GridView scroll container. Shows
// on hover AND keyboard focus; the preview itself is pointer-events:none.
export function HoverCard({ card, children }: Props): JSX.Element {
  const ref = useRef<HTMLDivElement>(null)
  const [rect, setRect] = useState<DOMRect | null>(null)

  const show = (): void => {
    if (ref.current) setRect(ref.current.getBoundingClientRect())
  }
  const hide = (): void => setRect(null)

  return (
    <div
      ref={ref}
      className={s.wrap}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
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
