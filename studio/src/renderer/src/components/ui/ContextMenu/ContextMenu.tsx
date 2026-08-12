import { useEffect, useRef, useState } from 'react'
import styles from './ContextMenu.module.css'

interface ContextMenuItem {
  label: string
  onClick: () => void
  destructive?: boolean
}

interface ContextMenuProps {
  items: ContextMenuItem[]
  position: { x: number; y: number }
  onClose: () => void
}

function ContextMenu({ items, position, onClose }: ContextMenuProps): JSX.Element {
  const ref = useRef<HTMLDivElement>(null)
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([])
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)

  useEffect(() => {
    if (ref.current) {
      ref.current.style.setProperty('--menu-top', position.y + 'px')
      ref.current.style.setProperty('--menu-left', position.x + 'px')
    }
  }, [position])

  useEffect(() => {
    function handleMouseDown(e: MouseEvent): void {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose()
      }
    }
    function handleKeyDown(e: KeyboardEvent): void {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', handleMouseDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleMouseDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [onClose])

  useEffect(() => {
    itemRefs.current[0]?.focus()
  }, [])

  function handleContainerKeyDown(e: React.KeyboardEvent<HTMLDivElement>): void {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHoveredIndex((prev) => {
        const next = ((prev ?? -1) + 1) % items.length
        itemRefs.current[next]?.focus()
        return next
      })
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHoveredIndex((prev) => {
        const next = ((prev ?? 0) - 1 + items.length) % items.length
        itemRefs.current[next]?.focus()
        return next
      })
    } else if (e.key === 'Home') {
      e.preventDefault()
      setHoveredIndex(0)
      itemRefs.current[0]?.focus()
    } else if (e.key === 'End') {
      e.preventDefault()
      setHoveredIndex(items.length - 1)
      itemRefs.current[items.length - 1]?.focus()
    }
  }

  return (
    <div ref={ref} role="menu" className={styles.menu} onKeyDown={handleContainerKeyDown}>
      {items.map((item, i) => (
        <button
          key={i}
          type="button"
          role="menuitem"
          tabIndex={-1}
          ref={(el) => { itemRefs.current[i] = el }}
          className={styles.item}
          data-hovered={hoveredIndex === i ? 'true' : undefined}
          data-destructive={item.destructive ? 'true' : undefined}
          onMouseEnter={() => setHoveredIndex(i)}
          onMouseLeave={() => setHoveredIndex(null)}
          onClick={() => {
            onClose()
            item.onClick()
          }}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}
