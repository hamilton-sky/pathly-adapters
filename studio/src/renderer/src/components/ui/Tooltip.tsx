import { useState, useRef, useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useTheme } from '../../useTheme'

interface TooltipProps {
  label: string
  shortcut?: string
  children: ReactNode
  placement?: 'top' | 'bottom' | 'left' | 'right'
  delay?: number
}

export function Tooltip({
  label,
  shortcut,
  children,
  placement = 'top',
  delay = 400,
}: TooltipProps): JSX.Element {
  const [visible, setVisible] = useState(false)
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const wrapRef = useRef<HTMLSpanElement>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const t = useTheme()

  function show(): void {
    timerRef.current = setTimeout(() => {
      // display:contents has no box — read from the first rendered child instead
      const el = (wrapRef.current?.firstElementChild as HTMLElement | null) ?? wrapRef.current
      if (!el) return
      const r = el.getBoundingClientRect()
      const GAP = 7
      let top: number, left: number
      if (placement === 'bottom')     { top = r.bottom + GAP; left = r.left + r.width / 2 }
      else if (placement === 'left')  { top = r.top + r.height / 2; left = r.left - GAP }
      else if (placement === 'right') { top = r.top + r.height / 2; left = r.right + GAP }
      else                            { top = r.top - GAP;    left = r.left + r.width / 2 }
      setPos({ top, left })
      setVisible(true)
    }, delay)
  }

  function hide(): void {
    if (timerRef.current) clearTimeout(timerRef.current)
    setVisible(false)
  }

  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current) }, [])

  const transform =
    placement === 'bottom' ? 'translate(-50%, 0)'                  :
    placement === 'left'   ? 'translate(calc(-100% - 2px), -50%)' :
    placement === 'right'  ? 'translate(2px, -50%)'               :
                             'translate(-50%, calc(-100% - 2px))'

  return (
    <span ref={wrapRef} onMouseEnter={show} onMouseLeave={hide} style={{ display: 'contents' }}>
      {children}
      {visible && createPortal(
        <div
          role="tooltip"
          style={{
            position: 'fixed',
            top: pos.top,
            left: pos.left,
            transform,
            zIndex: 99999,
            pointerEvents: 'none',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 7,
            backgroundColor: t.bgSurface1,
            color: t.textPrimary,
            padding: '5px 10px',
            borderRadius: 6,
            fontSize: 12,
            fontFamily: t.fontFamilyBase,
            whiteSpace: 'nowrap',
            boxShadow: '0 4px 18px rgba(0,0,0,0.5)',
            border: `1px solid rgba(255,255,255,0.07)`,
            lineHeight: 1.4,
          }}
        >
          {label}
          {shortcut && (
            <kbd
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                backgroundColor: t.bgBase,
                color: t.textMuted,
                border: `1px solid rgba(255,255,255,0.12)`,
                borderRadius: 4,
                padding: '1px 6px',
                fontFamily: t.fontFamilyMono,
                fontSize: 11,
                lineHeight: 1.5,
                letterSpacing: '0.03em',
              }}
            >
              {shortcut}
            </kbd>
          )}
        </div>,
        document.body,
      )}
    </span>
  )
}
