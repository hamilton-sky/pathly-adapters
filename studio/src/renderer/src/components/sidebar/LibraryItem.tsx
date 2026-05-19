import { FileText, GripVertical } from 'lucide-react'
import type { PathlyItem } from '../../types'
import styles from './Sidebar.module.css'

interface Props {
  item: PathlyItem
  isSelected: boolean
  isCanvasDraggable: boolean
  deep?: boolean
  onSelect: () => void
  onDragStart?: (e: React.DragEvent) => void
  onGripPointerDown?: () => void
}

export function LibraryItem({ item, isSelected, isCanvasDraggable, deep, onSelect, onDragStart, onGripPointerDown }: Props): JSX.Element {
  const cls = [
    styles.systemItemRow,
    deep ? styles.systemItemRowDeep : '',
    isSelected ? styles.systemItemRowSelected : '',
  ].filter(Boolean).join(' ')

  return (
    <button
      className={cls}
      draggable={isCanvasDraggable}
      onClick={onSelect}
      onDragStart={onDragStart}
      title={item.path}
    >
      {isCanvasDraggable && (
        <span
          className={styles.grip}
          onPointerDown={onGripPointerDown}
          title="Drag to canvas"
        >
          <GripVertical size={12} />
        </span>
      )}
      <FileText size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
      <span className={styles.itemName}>{item.name}</span>
    </button>
  )
}
