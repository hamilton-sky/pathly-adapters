import React, { useState, useEffect, useRef } from 'react'
import {
  GripVertical, ChevronUp, ChevronDown, MoreHorizontal, X,
} from 'lucide-react'
import styles from './FragmentCell.module.css'
import { useSkillNotebookStore } from '../../../store/skillNotebookStore'

interface Props {
  id: string
  fragmentName: string
  category: string
  description: string
  isNew?: boolean
  isFirst?: boolean
  isLast?: boolean
  onMoveUp?: () => void
  onMoveDown?: () => void
}

const CATEGORY_CLASS: Record<string, string> = {
  core: styles.badgeCore,
  flow: styles.badgeFlow,
  integration: styles.badgeIntegration,
}

export default function FragmentCell({ id, fragmentName, category, description, isNew = false, isFirst = false, isLast = false, onMoveUp, onMoveDown }: Props) {
  const removeCell = useSkillNotebookStore(s => s.removeCell)
  const [showNew, setShowNew] = useState(isNew)
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!showNew) return
    const t = setTimeout(() => setShowNew(false), 150)
    return () => clearTimeout(t)
  }, [showNew])

  useEffect(() => {
    if (!menuOpen) return
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  return (
    <div className={`${styles.cell} ${showNew ? styles.cellNew : ''}`}>
      <div className={styles.cellHead}>
        <div
          className={styles.grip}
          draggable
          onDragStart={e => {
            e.dataTransfer.setData('cell-id', id)
            e.dataTransfer.effectAllowed = 'move'
          }}
        >
          <GripVertical size={13} />
        </div>
        <span className={styles.name}>{fragmentName}</span>
        {category && (
          <span className={`${styles.badge} ${CATEGORY_CLASS[category] ?? ''}`}>
            {category.toUpperCase()}
          </span>
        )}
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.actionBtn}
            aria-label="Move up"
            title="Move up"
            disabled={isFirst}
            onClick={onMoveUp}
          >
            <ChevronUp size={13} />
          </button>
          <button
            type="button"
            className={styles.actionBtn}
            aria-label="Move down"
            title="Move down"
            disabled={isLast}
            onClick={onMoveDown}
          >
            <ChevronDown size={13} />
          </button>
          <div className={styles.menuWrap} ref={menuRef}>
            <button
              type="button"
              className={`${styles.actionBtn} ${menuOpen ? styles.actionBtnActive : ''}`}
              aria-label="More options"
              onClick={() => setMenuOpen(o => !o)}
            >
              <MoreHorizontal size={13} />
            </button>
            {menuOpen && (
              <div className={styles.menu} role="menu">
                <button
                  type="button"
                  className={styles.menuItem}
                  role="menuitem"
                  disabled={isFirst}
                  onClick={() => { onMoveUp?.(); setMenuOpen(false) }}
                >
                  Move up
                </button>
                <button
                  type="button"
                  className={styles.menuItem}
                  role="menuitem"
                  disabled={isLast}
                  onClick={() => { onMoveDown?.(); setMenuOpen(false) }}
                >
                  Move down
                </button>
                <div className={styles.menuDivider} />
                <button
                  type="button"
                  className={`${styles.menuItem} ${styles.menuItemDanger}`}
                  role="menuitem"
                  onClick={() => { removeCell(id); setMenuOpen(false) }}
                >
                  Delete
                </button>
              </div>
            )}
          </div>
          <button
            type="button"
            className={`${styles.actionBtn} ${styles.removeBtn}`}
            onClick={() => removeCell(id)}
            title="Remove fragment"
            aria-label="Remove fragment"
          >
            <X size={13} />
          </button>
        </div>
      </div>
      {description && (
        <div className={styles.cellBody}>
          <div className={styles.description}>{description}</div>
        </div>
      )}
    </div>
  )
}
