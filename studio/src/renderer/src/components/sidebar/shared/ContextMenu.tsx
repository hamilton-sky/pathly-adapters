import { useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import styles from '../Sidebar.module.css'

interface ContextMenuProps {
  anchor: DOMRect
  onClose: () => void
  children: React.ReactNode
}

export function ContextMenu({ anchor, onClose, children }: ContextMenuProps): JSX.Element {
  const menuRef = useRef<HTMLDivElement>(null)
  const x = anchor.right + 4
  const y = Math.min(anchor.top, window.innerHeight - 200)

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

  return createPortal(
    <div
      ref={menuRef}
      className={styles.contextMenuPortal}
      style={{ left: x, top: y }}
    >
      {children}
    </div>,
    document.body
  )
}
