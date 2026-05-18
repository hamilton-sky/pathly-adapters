import { useEffect, useRef, useState } from 'react'
import { useTheme } from '../../useTheme'

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

export function ContextMenu({ items, position, onClose }: ContextMenuProps): JSX.Element {
  const t = useTheme()
  const ref = useRef<HTMLDivElement>(null)
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)

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

  const menuStyle: React.CSSProperties = {
    position: 'fixed',
    top: position.y,
    left: position.x,
    background: t.bgSurface0,
    border: `1px solid ${t.bgSurface1}`,
    borderRadius: '4px',
    zIndex: 9999,
    fontFamily: 'monospace',
    fontSize: '12px',
    padding: '4px 0',
    minWidth: '120px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
  }

  return (
    <div ref={ref} style={menuStyle}>
      {items.map((item, i) => {
        const isHovered = hoveredIndex === i
        const color = item.destructive
          ? isHovered ? t.red : t.textSecondary
          : isHovered ? t.textPrimary : t.textSecondary

        const itemStyle: React.CSSProperties = {
          display: 'block',
          width: '100%',
          background: isHovered ? t.bgSurface1 : 'none',
          border: 'none',
          color,
          cursor: 'pointer',
          padding: '5px 14px',
          textAlign: 'left',
          fontSize: '12px',
          fontFamily: 'monospace',
          boxSizing: 'border-box',
        }

        return (
          <button
            key={i}
            style={itemStyle}
            onMouseEnter={() => setHoveredIndex(i)}
            onMouseLeave={() => setHoveredIndex(null)}
            onClick={() => {
              onClose()
              item.onClick()
            }}
          >
            {item.label}
          </button>
        )
      })}
    </div>
  )
}
