import React, { useState, useEffect, useRef } from 'react'
import { ChevronUp, ChevronDown, MoreHorizontal, Copy, Diamond, Trash2 } from 'lucide-react'
import { Tooltip } from '../../ui'
import styles from './FragmentCell.module.css'
import { useSkillNotebookStore } from '../../../store/skillNotebookStore'

interface Props {
  id: string
  fragmentName: string
  category: string
  description: string
  path?: string
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

export default function FragmentCell({
  id, fragmentName, category, description, path,
  isNew = false, isFirst = false, isLast = false,
  onMoveUp, onMoveDown,
}: Props) {
  const removeCell = useSkillNotebookStore(s => s.removeCell)
  const [showNew, setShowNew]   = useState(isNew)
  const [menuOpen, setMenuOpen] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  const isLong = description.length > 200
  const displayDesc = isLong && !expanded ? description.slice(0, 200).trimEnd() + 'â€¦' : description

  useEffect(() => {
    if (!showNew) return
    const t = setTimeout(() => setShowNew(false), 150)
    return () => clearTimeout(t)
  }, [showNew])

  useEffect(() => {
    if (!menuOpen) return
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  return (
    <div className={`${styles.cell} ${showNew ? styles.cellNew : ''}`}>
      <div className={styles.cellHead}>
        <span className={styles.name}>{fragmentName}</span>
        {category && (
          <span className={`${styles.badge} ${CATEGORY_CLASS[category] ?? ''}`}>
            {category.toUpperCase()}
          </span>
        )}
        <div className={styles.actions}>
          <Tooltip label="Move up" placement="top">
            <button type="button" className={styles.actionBtn} aria-label="Move up" disabled={isFirst} onClick={onMoveUp}>
              <ChevronUp size={15} />
            </button>
          </Tooltip>
          <Tooltip label="Move down" placement="top">
            <button type="button" className={styles.actionBtn} aria-label="Move down" disabled={isLast} onClick={onMoveDown}>
              <ChevronDown size={15} />
            </button>
          </Tooltip>
          <div className={styles.menuWrap} ref={menuRef}>
            <Tooltip label="More options" placement="top">
              <button
                type="button"
                className={`${styles.actionBtn} ${menuOpen ? styles.actionBtnActive : ''}`}
                aria-label="More options"
                {...(menuOpen ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
                onClick={() => setMenuOpen(o => !o)}
              >
                <MoreHorizontal size={15} />
              </button>
            </Tooltip>
            {menuOpen && (
              <div className={styles.menu} role="menu">
                <button type="button" className={styles.menuItem} role="menuitem" onClick={() => setMenuOpen(false)}>
                  <Copy size={15} className={styles.menuIcon} />Duplicate<span className={styles.menuKbd}>âŒ˜D</span>
                </button>
                <button type="button" className={styles.menuItem} role="menuitem" disabled={isFirst} onClick={() => { onMoveUp?.(); setMenuOpen(false) }}>
                  <ChevronUp size={15} className={styles.menuIcon} />Move up<span className={styles.menuKbd}>âŒ˜â†‘</span>
                </button>
                <button type="button" className={styles.menuItem} role="menuitem" disabled={isLast} onClick={() => { onMoveDown?.(); setMenuOpen(false) }}>
                  <ChevronDown size={15} className={styles.menuIcon} />Move down<span className={styles.menuKbd}>âŒ˜â†"</span>
                </button>
                <button type="button" className={styles.menuItem} role="menuitem" onClick={() => setMenuOpen(false)}>
                  <Diamond size={15} className={styles.menuIcon} />Convert to body
                </button>
                <div className={styles.menuDivider} />
                <button type="button" className={`${styles.menuItem} ${styles.menuItemDanger}`} role="menuitem" onClick={() => { removeCell(id); setMenuOpen(false) }}>
                  <Trash2 size={15} className={styles.menuIcon} />Delete<span className={styles.menuKbd}>âŒ«</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
      {description && (
        <div className={styles.cellBody}>
          <div className={styles.description}>{displayDesc}</div>
          {isLong && (
            <button type="button" className={styles.toggle} onClick={() => setExpanded(v => !v)}>
              {expanded ? 'â–´ Collapse' : 'â–¾ Show more'}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
