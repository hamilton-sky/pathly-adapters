import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import styles from './Sidebar.module.css'

interface ContextMenuProps {
  anchor: DOMRect
  sidebarWidth: number
  onClose: () => void
  children: React.ReactNode
}

export function ContextMenu({ anchor, sidebarWidth, onClose, children }: ContextMenuProps): JSX.Element {
  const [pos, setPos] = useState({ x: sidebarWidth + 4, y: Math.min(anchor.top, window.innerHeight - 200) })
  const dragging = useRef(false)
  const dragOffset = useRef({ x: 0, y: 0 })
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onOutside(e: MouseEvent): void {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) onClose()
    }
    function onEscape(e: KeyboardEvent): void {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', onOutside)
    document.addEventListener('keydown', onEscape)
    return () => {
      document.removeEventListener('mousedown', onOutside)
      document.removeEventListener('keydown', onEscape)
    }
  }, [onClose])

  function onDragHandleMouseDown(e: React.MouseEvent): void {
    e.preventDefault()
    dragging.current = true
    dragOffset.current = { x: e.clientX - pos.x, y: e.clientY - pos.y }

    function onMouseMove(ev: MouseEvent): void {
      if (!dragging.current) return
      setPos({ x: ev.clientX - dragOffset.current.x, y: ev.clientY - dragOffset.current.y })
    }
    function onMouseUp(): void {
      dragging.current = false
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }

  return createPortal(
    <div
      ref={menuRef}
      className={styles.contextMenuPortal}
      style={{ left: pos.x, top: pos.y }}
    >
      <div
        className={styles.menuDragHandle}
        onMouseDown={onDragHandleMouseDown}
      >
        ⠿
      </div>
      {children}
    </div>,
    document.body
  )
}
