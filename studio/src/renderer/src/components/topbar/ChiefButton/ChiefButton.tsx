import React, { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Crown } from 'lucide-react'
import { Tooltip } from '../../ui'
import { useProjectStore } from '../../../store/projectStore'
import { ChiefLauncher } from './ChiefLauncher/ChiefLauncher'
import { ChiefNotices } from './ChiefNotices/ChiefNotices'
import { useChiefNotices } from './hooks/useChiefNotices'
import type { ChiefNotice } from '../../../services/chiefApi'
import styles from './ChiefButton.module.css'

const POPOVER_WIDTH = 320

interface Props {
  compact: boolean
}

/** Top-bar Chief button: opens the launcher for the current project's chief, with a badge for the
 *  chief's runs that ended unread; opening it lists them and marks them read. */
export function ChiefButton({ compact }: Props): JSX.Element {
  const projectRoot = useProjectStore((st) => st.projectPath)
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const popRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const { notices, markRead } = useChiefNotices(projectRoot)
  const [shown, setShown] = useState<ChiefNotice[]>([])

  function toggle(): void {
    if (!open) {
      setShown(notices)
      void markRead(notices.map((n) => n.run_id))
    }
    setOpen(!open)
  }

  // Below the trigger, right-aligned to it, clamped inside the window. Portaled to <body>.
  useLayoutEffect(() => {
    if (!open || !triggerRef.current) return
    const r = triggerRef.current.getBoundingClientRect()
    const left = Math.max(8, Math.min(r.right - POPOVER_WIDTH, window.innerWidth - POPOVER_WIDTH - 8))
    setPos({ top: r.bottom + 6, left })
  }, [open])

  useEffect(() => {
    if (!open) return
    function onDown(e: MouseEvent): void {
      const t = e.target as Node
      // BoardSelect portals its menu outside the popover — clicks there must not close.
      if (t instanceof Element && t.closest('[data-board-select-menu]')) return
      if (popRef.current?.contains(t) || triggerRef.current?.contains(t)) return
      setOpen(false)
    }
    function onKey(e: KeyboardEvent): void {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const label = projectRoot ? 'Chief' : 'Chief — open a project first'
  const unread = notices.length
  const unreadText = `${unread} finished chief run${unread === 1 ? '' : 's'} unread`

  return (
    <div className={styles.wrapper}>
      <Tooltip label={label} placement="bottom">
        <button
          ref={triggerRef}
          type="button"
          className={styles.trigger}
          data-testid="topbar-chief"
          disabled={!projectRoot}
          onClick={toggle}
          aria-label={unread > 0 ? `Open the chief launcher (${unreadText})` : 'Open the chief launcher'}
          {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        >
          <Crown size={14} />
          {!compact && <span className={styles.text}>Chief</span>}
          {unread > 0 && (
            <span className={styles.badge} data-testid="topbar-chief-badge" aria-hidden="true">
              {unread}
            </span>
          )}
        </button>
      </Tooltip>

      {open &&
        createPortal(
          <div
            ref={popRef}
            className={styles.popover}
            style={{ '--pop-top': `${pos.top}px`, '--pop-left': `${pos.left}px` } as React.CSSProperties}
            role="dialog"
            aria-label="Chief"
          >
            {shown.length > 0 && <ChiefNotices notices={shown} />}
            <ChiefLauncher projectRoot={projectRoot} onOpened={() => setOpen(false)} />
          </div>,
          document.body,
        )}
    </div>
  )
}
