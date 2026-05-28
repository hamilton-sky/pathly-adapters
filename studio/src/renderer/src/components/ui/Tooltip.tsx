import { useState, useRef, useEffect, useLayoutEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useTheme } from '../../useTheme'

interface TooltipProps {
  label: string
  description?: string
  shortcut?: string
  children: ReactNode
  placement?: 'top' | 'bottom' | 'left' | 'right'
  delay?: number
}

export function Tooltip({
  label,
  description,
  shortcut,
  children,
  placement = 'top',
  delay = 400,
}: TooltipProps): JSX.Element {
  const [visible, setVisible] = useState(false)
  const [rawPos, setRawPos] = useState({ top: 0, left: 0 })
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const [resolvedPlacement, setResolvedPlacement] = useState(placement)
  const wrapRef = useRef<HTMLSpanElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const t = useTheme()

  function getAnchorEl(root: HTMLElement): HTMLElement {
    // display:contents spans have zero-size BCR; walk down until we find a real box
    let el: HTMLElement = root
    while (el.getBoundingClientRect().width === 0 && el.getBoundingClientRect().height === 0) {
      const child = el.firstElementChild as HTMLElement | null
      if (!child) break
      el = child
    }
    return el
  }

  function show(): void {
    timerRef.current = setTimeout(() => {
      if (!wrapRef.current) return
      const el = getAnchorEl(wrapRef.current)
      const r = el.getBoundingClientRect()
      const GAP = 7
      let top: number, left: number, rp = placement
      if (placement === 'bottom')     { top = r.bottom + GAP; left = r.left + r.width / 2 }
      else if (placement === 'left')  { top = r.top + r.height / 2; left = r.left - GAP }
      else if (placement === 'right') { top = r.top + r.height / 2; left = r.right + GAP }
      else                            { top = r.top - GAP; left = r.left + r.width / 2; rp = 'top' }
      setRawPos({ top, left })
      setResolvedPlacement(rp)
      setPos({ top, left })
      setVisible(true)
    }, delay)
  }

  function hide(): void {
    if (timerRef.current) clearTimeout(timerRef.current)
    setVisible(false)
  }

  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current) }, [])

  // After the tooltip renders, measure it and clamp to viewport
  useLayoutEffect(() => {
    if (!visible || !tooltipRef.current) return
    const el = tooltipRef.current
    const r = el.getBoundingClientRect()
    const PAD = 8
    const vw = window.innerWidth
    const vh = window.innerHeight
    let { top, left } = rawPos
    let rp = resolvedPlacement

    if (rp === 'top' || rp === 'bottom') {
      // Clamp horizontal: tooltip is center-anchored at left
      const halfW = r.width / 2
      if (left + halfW > vw - PAD) left = vw - PAD - halfW
      if (left - halfW < PAD) left = PAD + halfW
      // Flip top→bottom if it would go above viewport
      if (rp === 'top' && top - r.height < PAD) {
        const el2 = (wrapRef.current?.firstElementChild as HTMLElement | null) ?? wrapRef.current
        if (el2) { const rb = el2.getBoundingClientRect(); top = rb.bottom + 7; rp = 'bottom' }
      }
      // Flip bottom→top if it would go below viewport
      if (rp === 'bottom' && top + r.height > vh - PAD) {
        const el2 = (wrapRef.current?.firstElementChild as HTMLElement | null) ?? wrapRef.current
        if (el2) { const rb = el2.getBoundingClientRect(); top = rb.top - 7; rp = 'top' }
      }
    }

    setResolvedPlacement(rp)
    setPos({ top, left })
  }, [visible, rawPos, resolvedPlacement])

  const transform =
    resolvedPlacement === 'bottom' ? 'translate(-50%, 0)'                  :
    resolvedPlacement === 'left'   ? 'translate(calc(-100% - 2px), -50%)' :
    resolvedPlacement === 'right'  ? 'translate(2px, -50%)'               :
                                     'translate(-50%, calc(-100% - 2px))'

  return (
    <span ref={wrapRef} onMouseEnter={show} onMouseLeave={hide} style={{ display: 'contents' }}>
      {children}
      {visible && createPortal(
        <div
          ref={tooltipRef}
          role="tooltip"
          style={{
            position: 'fixed',
            top: pos.top,
            left: pos.left,
            transform,
            zIndex: 99999,
            pointerEvents: 'none',
            display: 'inline-flex',
            flexDirection: description ? 'column' : 'row',
            alignItems: description ? 'flex-start' : 'center',
            gap: description ? 3 : 7,
            backgroundColor: t.bgSurface1,
            color: t.textPrimary,
            padding: '6px 10px',
            borderRadius: 6,
            fontSize: 12,
            fontFamily: t.fontFamilyBase,
            whiteSpace: description ? 'normal' : 'nowrap',
            maxWidth: description ? 220 : undefined,
            boxShadow: '0 4px 18px rgba(0,0,0,0.5)',
            border: `1px solid rgba(255,255,255,0.07)`,
            lineHeight: 1.4,
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: 7, whiteSpace: 'nowrap' }}>
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
          </span>
          {description && (
            <span style={{ fontSize: 11, color: t.textMuted, lineHeight: 1.4 }}>
              {description}
            </span>
          )}
        </div>,
        document.body,
      )}
    </span>
  )
}
