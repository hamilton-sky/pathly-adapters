import React, { useState, useRef, useCallback, useEffect } from 'react'
import {
  Pencil, Check, ChevronUp, ChevronDown, MoreHorizontal,
  Copy, Diamond, Trash2, RotateCcw, SquareDashedMousePointer, Code, Bold, Italic, Columns, Scissors,
} from 'lucide-react'
import { Tooltip } from '../../ui'
import MarkdownRenderer from '../../shared/MarkdownRenderer/MarkdownRenderer'
import SkillSplitModal from '../../shared/SkillSplitModal/SkillSplitModal'
import { applyInlineFormat, type InlineFormat } from '../../shared/markdownInline'
import { useMarkdownEditorStore } from '../../../store/markdownEditorStore'
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
  const updateBodyCell = useMarkdownEditorStore(s => s.updateBodyCell)
  const insertBodyCell = useMarkdownEditorStore(s => s.insertBodyCell)
  const splitBodyCell  = useMarkdownEditorStore(s => s.splitBodyCell)
  const duplicateCell  = useMarkdownEditorStore(s => s.duplicateCell)

  const [cellMode, setCellMode]         = useState<CellMode>('view')
  const [draft, setDraft]               = useState(content)
  const [headingDraft, setHeadingDraft] = useState(() => heading.replace(/^#{1,6}\s+/, ''))
  const [expanded, setExpanded]       = useState(false)
  const [menuOpen, setMenuOpen]       = useState(false)
  const [showSplitModal, setShowSplitModal] = useState(false)
  const [selBar, setSelBar]           = useState<SelBar | null>(null)

  const bodyRef = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

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

  function applyFormat(format: InlineFormat) {
    const ta = textareaRef.current
    if (!ta) return
    const next = applyInlineFormat(format, draft, ta.selectionStart, ta.selectionEnd)
    setDraft(next.text)
    // Restore the selection after React re-renders the textarea value
    requestAnimationFrame(() => { ta.focus(); ta.setSelectionRange(next.selStart, next.selEnd) })
  }

  function handleEditorKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { commitEdit(); return }
    if (!(e.metaKey || e.ctrlKey)) return
    const k = e.key.toLowerCase()
    if (k === 'b')          { e.preventDefault(); applyFormat('bold') }
    else if (k === 'i')     { e.preventDefault(); applyFormat('italic') }
    else if (e.key === '`') { e.preventDefault(); applyFormat('code') }
  }

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

  const formatBar = (
    <div className={styles.fmtBar}>
      <Tooltip label="Bold" shortcut="Ctrl+B" placement="top">
        <button type="button" className={styles.fmtBtn} aria-label="Bold" onMouseDown={e => e.preventDefault()} onClick={() => applyFormat('bold')}>
          <Bold size={13} />
        </button>
      </Tooltip>
      <Tooltip label="Italic" shortcut="Ctrl+I" placement="top">
        <button type="button" className={styles.fmtBtn} aria-label="Italic" onMouseDown={e => e.preventDefault()} onClick={() => applyFormat('italic')}>
          <Italic size={13} />
        </button>
      </Tooltip>
      <Tooltip label="Wrap in code" shortcut="Ctrl+`" placement="top">
        <button type="button" className={styles.fmtBtn} aria-label="Wrap in code" onMouseDown={e => e.preventDefault()} onClick={() => applyFormat('code')}>
          <Code size={13} />
        </button>
      </Tooltip>
    </div>
  )

  return (
    <div
      className={`${styles.cell} ${isSystem ? styles.cellSystem : styles.cellBodyType}${menuOpen ? ` ${styles.cellMenuOpen}` : ''}`}
      tabIndex={-1}
    >
      {/* â"€â"€ strip: badge + actions sit ON the top border line â"€â"€ */}
      <div className={styles.strip}>
        <span className={styles.typeBadge}>{isSystem ? 'system' : 'body'}</span>

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

        <span className={styles.stripDiv} />

        <Tooltip label="Split view (edit + preview)" placement="top">
          <button
            type="button"
            className={`${styles.actionBtn} ${cellMode === 'split' ? styles.actionBtnActive : ''}`}
            aria-label="Toggle split view"
            onClick={handleSplitClick}
          >
            <Columns size={15} />
          </button>
        </Tooltip>

        {!isEditing ? (
          <Tooltip label="Edit" placement="top">
            <button type="button" className={styles.actionBtn} aria-label="Edit" onClick={handleEditClick}>
              <Pencil size={15} />
            </button>
          </Tooltip>
        ) : (
          <Tooltip label="Save" shortcut="Ctrl+Enter" placement="top">
            <button type="button" className={`${styles.actionBtn} ${styles.actionBtnSave}`} aria-label="Save" onClick={commitEdit}>
              <Check size={15} />
            </button>
          </Tooltip>
        )}

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
              <button type="button" className={styles.menuItem} role="menuitem" onClick={() => { duplicateCell(id); setMenuOpen(false) }}>
                <Copy size={15} className={styles.menuIcon} />Duplicate<span className={styles.menuKbd}>⌘D</span>
              </button>
              <button type="button" className={styles.menuItem} role="menuitem" disabled={isFirst} onClick={() => { onMoveUp?.(); setMenuOpen(false) }}>
                <ChevronUp size={15} className={styles.menuIcon} />Move up<span className={styles.menuKbd}>⌘↑</span>
              </button>
              <button type="button" className={styles.menuItem} role="menuitem" disabled={isLast} onClick={() => { onMoveDown?.(); setMenuOpen(false) }}>
                <ChevronDown size={15} className={styles.menuIcon} />Move down<span className={styles.menuKbd}>⌘↓</span>
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
                  <Trash2 size={15} className={styles.menuIcon} />Delete<span className={styles.menuKbd}>⌫</span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* â"€â"€ heading â"€â"€ */}
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

      {/* â"€â"€ body â"€â"€ */}
      {cellMode === 'split' ? (
        <div className={styles.splitBody}>
          <div className={styles.splitEdit}>
            {formatBar}
            <textarea
              ref={textareaRef}
              className={styles.editor}
              value={draft}
              aria-label="Cell content editor"
              onChange={e => setDraft(e.target.value)}
              onKeyDown={handleEditorKeyDown}
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
            <>
              {formatBar}
              <textarea
                ref={textareaRef}
                className={styles.editor}
                value={draft}
                aria-label="Cell content editor"
                onChange={e => setDraft(e.target.value)}
                onKeyDown={handleEditorKeyDown}
                autoFocus
                rows={Math.max(4, draft.split('\n').length + 1)}
              />
            </>
          ) : (
            <>
              <MarkdownRenderer content={preview} />
              {isLong && (
                <button type="button" className={styles.toggle} onClick={() => setExpanded(v => !v)}>
                  {expanded ? '▴ Collapse' : '▾ Show full content'}
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
                <SquareDashedMousePointer size={12} /><span>New cell from selection</span>
              </button>
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
