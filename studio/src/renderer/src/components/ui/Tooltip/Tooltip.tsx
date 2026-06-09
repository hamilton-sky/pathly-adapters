import { useState, useRef, useEffect, useLayoutEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import clsx from 'clsx'
import styles from './Tooltip.module.css'

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
          className={clsx(styles.tooltip, description && styles.multiline)}
          style={{ top: pos.top, left: pos.left, transform }}
        >
          <span className={styles.labelRow}>
            {label}
          {shortcut && (
            <kbd className={styles.kbd}>
              {shortcut}
            </kbd>
          )}
          </span>
          {description && (
            <span className={styles.desc}>
              {description}
            </span>
          )}
        </div>,
        document.body,
      )}
    </span>
  )
}
