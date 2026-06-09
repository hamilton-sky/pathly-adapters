import React, { useState, useRef, useCallback, useEffect } from 'react'
import {
  Pencil, Check, ChevronUp, ChevronDown, MoreHorizontal,
  Copy, Diamond, Trash2, RotateCcw, Sparkles, Code, Bold, Italic, Columns, Scissors,
} from 'lucide-react'
import MarkdownRenderer from '../../shared/MarkdownRenderer/MarkdownRenderer'
import SkillSplitModal from '../../shared/SkillSplitModal/SkillSplitModal'
import { useSkillNotebookStore } from '../../../store/skillNotebookStore'
import styles from './BodyCell.module.css'

type CellMode = 'view' | 'edit' | 'split'

interface Props {
  id: string
  heading: string
  content: string
  isSystem?: boolean
  isFirst?: boolean
  isLast?: boolean
  onMoveUp?: () => void
  onMoveDown?: () => void
  onRemove?: () => void
  onRevert?: () => void
}

interface SelBar { x: number; y: number; text: string }

export default function BodyCell({
  id, heading, content,
  isSystem = false, isFirst = false, isLast = false,
  onMoveUp, onMoveDown, onRemove, onRevert,
}: Props) {
  const updateBodyCell = useSkillNotebookStore(s => s.updateBodyCell)
  const insertBodyCell = useSkillNotebookStore(s => s.insertBodyCell)
  const splitBodyCell  = useSkillNotebookStore(s => s.splitBodyCell)

  const [cellMode, setCellMode]         = useState<CellMode>('view')
  const [draft, setDraft]               = useState(content)
  const [headingDraft, setHeadingDraft] = useState(() => heading.replace(/^#{1,6}\s+/, ''))
  const [expanded, setExpanded]       = useState(false)
  const [menuOpen, setMenuOpen]       = useState(false)
  const [showSplitModal, setShowSplitModal] = useState(false)
  const [selBar, setSelBar]           = useState<SelBar | null>(null)

  const bodyRef = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  const isEditing = cellMode === 'edit' || cellMode === 'split'
  const isLong    = content.split('\n').length > 6
  const preview   = isLong && !expanded && cellMode === 'view'
    ? content.split('\n').slice(0, 6).join('\n')
    : content

  // Strip leading markdown heading prefix for display (## â†’ plain title)
  const displayTitle = heading.replace(/^#{1,6}\s+/, '')

  useEffect(() => {
    if (!menuOpen) return
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  function commitEdit() { updateBodyCell(id, draft, headingDraft); setCellMode('view') }
  function handleEditClick() { setDraft(content); setHeadingDraft(displayTitle); setCellMode('edit') }
  function handleSplitClick() { setDraft(content); setHeadingDraft(displayTitle); setCellMode(cellMode === 'split' ? 'view' : 'split') }

  const handleMouseUp = useCallback(() => {
    if (cellMode !== 'view') return
    const sel = window.getSelection()
    if (!sel || sel.isCollapsed || !sel.toString().trim()) { setSelBar(null); return }
    const range = sel.getRangeAt(0)
    const rect  = range.getBoundingClientRect()
    const cRect = bodyRef.current?.getBoundingClientRect()
    if (!cRect) return
    setSelBar({ x: rect.left + rect.width / 2 - cRect.left, y: rect.top - cRect.top - 4, text: sel.toString() })
  }, [cellMode])

  function handleNewCellFromSelection() {
    if (!selBar) return
    insertBodyCell('New section', selBar.text.trim(), id)
    setSelBar(null)
    window.getSelection()?.removeAllRanges()
  }

  return (
    <div
      className={`${styles.cell} ${isSystem ? styles.cellSystem : styles.cellBodyType}${menuOpen ? ` ${styles.cellMenuOpen}` : ''}`}
      tabIndex={-1}
    >
      {/* â”€â”€ strip: badge + actions sit ON the top border line â”€â”€ */}
      <div className={styles.strip}>
        <span className={styles.typeBadge}>{isSystem ? 'system' : 'body'}</span>

        <button type="button" className={styles.actionBtn} title="Move up" aria-label="Move up" disabled={isFirst} onClick={onMoveUp}>
          <ChevronUp size={15} />
        </button>
        <button type="button" className={styles.actionBtn} title="Move down" aria-label="Move down" disabled={isLast} onClick={onMoveDown}>
          <ChevronDown size={15} />
        </button>

        <span className={styles.stripDiv} />

        <button
          type="button"
          className={`${styles.actionBtn} ${cellMode === 'split' ? styles.actionBtnActive : ''}`}
          title="Split view (edit + preview)"
          aria-label="Toggle split view"
          onClick={handleSplitClick}
        >
          <Columns size={15} />
        </button>

        {!isEditing ? (
          <button type="button" className={styles.actionBtn} title="Edit" onClick={handleEditClick}>
            <Pencil size={15} />
          </button>
        ) : (
          <button type="button" className={`${styles.actionBtn} ${styles.actionBtnSave}`} title="Save (Ctrl+Enter)" onClick={commitEdit}>
            <Check size={15} />
          </button>
        )}

        <div className={styles.menuWrap} ref={menuRef}>
          <button
            type="button"
            className={`${styles.actionBtn} ${menuOpen ? styles.actionBtnActive : ''}`}
            aria-label="More options"
            {...(menuOpen ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
            onClick={() => setMenuOpen(o => !o)}
          >
            <MoreHorizontal size={15} />
          </button>
          {menuOpen && (
            <div className={styles.menu} role="menu">
              <button type="button" className={styles.menuItem} role="menuitem" onClick={() => setMenuOpen(false)}>
                <Copy size={15} className={styles.menuIcon} />Duplicate<span className={styles.menuKbd}>âŒ˜D</span>
              </button>
              <button type="button" className={styles.menuItem} role="menuitem" disabled={isFirst} onClick={() => { onMoveUp?.(); setMenuOpen(false) }}>
                <ChevronUp size={15} className={styles.menuIcon} />Move up<span className={styles.menuKbd}>âŒ˜â†‘</span>
              </button>
              <button type="button" className={styles.menuItem} role="menuitem" disabled={isLast} onClick={() => { onMoveDown?.(); setMenuOpen(false) }}>
                <ChevronDown size={15} className={styles.menuIcon} />Move down<span className={styles.menuKbd}>âŒ˜â†“</span>
              </button>
              <button type="button" className={styles.menuItem} role="menuitem" onClick={() => setMenuOpen(false)}>
                <Diamond size={15} className={styles.menuIcon} />Convert to fragment
              </button>
              <button type="button" className={styles.menuItem} role="menuitem" onClick={() => { setShowSplitModal(true); setMenuOpen(false) }}>
                <Scissors size={15} className={styles.menuIcon} />Split into cells
              </button>
              <div className={styles.menuDivider} />
              {isSystem ? (
                <button type="button" className={styles.menuItem} role="menuitem" onClick={() => { onRevert?.(); setMenuOpen(false) }}>
                  <RotateCcw size={15} className={styles.menuIcon} />Revert to original
                </button>
              ) : (
                <button type="button" className={`${styles.menuItem} ${styles.menuItemDanger}`} role="menuitem" onClick={() => { onRemove?.(); setMenuOpen(false) }}>
                  <Trash2 size={15} className={styles.menuIcon} />Delete<span className={styles.menuKbd}>âŒ«</span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* â”€â”€ heading â”€â”€ */}
      {isEditing ? (
        <input
          type="text"
          className={styles.cellTitleInput}
          value={headingDraft}
          onChange={e => setHeadingDraft(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) commitEdit() }}
          aria-label="Cell heading"
        />
      ) : (
        <div className={styles.cellTitle}>{displayTitle}</div>
      )}

      {/* â”€â”€ body â”€â”€ */}
      {cellMode === 'split' ? (
        <div className={styles.splitBody}>
          <div className={styles.splitEdit}>
            <textarea
              className={styles.editor}
              value={draft}
              onChange={e => setDraft(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) commitEdit() }}
              autoFocus
            />
          </div>
          <div className={styles.splitDivider} />
          <div className={styles.splitPreview}>
            <MarkdownRenderer content={draft} />
          </div>
        </div>
      ) : (
        <div className={styles.cellBody} ref={bodyRef} onMouseUp={handleMouseUp}>
          {cellMode === 'edit' ? (
            <textarea
              className={styles.editor}
              value={draft}
              onChange={e => setDraft(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) commitEdit() }}
              autoFocus
              rows={Math.max(4, draft.split('\n').length + 1)}
            />
          ) : (
            <>
              <MarkdownRenderer content={preview} />
              {isLong && (
                <button type="button" className={styles.toggle} onClick={() => setExpanded(v => !v)}>
                  {expanded ? 'â–´ Collapse' : 'â–¾ Show full content'}
                </button>
              )}
            </>
          )}
          {selBar && (
            <div
              className={styles.selBar}
              style={{ '--sel-x': `${selBar.x}px`, '--sel-y': `${selBar.y}px` } as React.CSSProperties}
              onMouseDown={e => e.preventDefault()}
            >
              <button type="button" className={styles.selBtn} onClick={handleNewCellFromSelection}>
                <Sparkles size={12} /><span>New cell from selection</span>
              </button>
              <span className={styles.selDivider} />
              <button type="button" className={styles.selBtnIcon} title="Insert as fragment" onClick={() => setSelBar(null)}><Diamond size={12} /></button>
              <button type="button" className={styles.selBtnIcon} title="Wrap in code" onClick={() => setSelBar(null)}><Code size={12} /></button>
              <button type="button" className={styles.selBtnIcon} title="Bold" onClick={() => setSelBar(null)}><Bold size={12} /></button>
              <button type="button" className={styles.selBtnIcon} title="Italic" onClick={() => setSelBar(null)}><Italic size={12} /></button>
            </div>
          )}
        </div>
      )}

      {showSplitModal && (
        <SkillSplitModal
          rawContent={content}
          onConfirm={(splitCells) => {
            splitBodyCell(id, splitCells.map(c => ({ heading: c.heading, content: c.content })))
            setShowSplitModal(false)
          }}
          onInsertOne={() => setShowSplitModal(false)}
          onClose={() => setShowSplitModal(false)}
        />
      )}
    </div>
  )
}
