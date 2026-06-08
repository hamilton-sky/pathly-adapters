import React, { useState, useRef, useCallback } from 'react'
import { Lock, Pencil, Check, ChevronUp, ChevronDown, Sparkles, Diamond, Code, Bold, Italic } from 'lucide-react'
import MarkdownRenderer from '../../shared/MarkdownRenderer/MarkdownRenderer'
import { useSkillNotebookStore } from '../../../store/skillNotebookStore'
import styles from './BodyCell.module.css'

interface Props {
  id: string
  heading: string
  content: string
  isFirst?: boolean
  isLast?: boolean
  onMoveUp?: () => void
  onMoveDown?: () => void
}

interface SelectionBar {
  x: number
  y: number
  text: string
}

export default function BodyCell({ id, heading, content, isFirst = false, isLast = false, onMoveUp, onMoveDown }: Props) {
  const updateBodyCell  = useSkillNotebookStore(s => s.updateBodyCell)
  const insertBodyCell  = useSkillNotebookStore(s => s.insertBodyCell)
  const [editing, setEditing]   = useState(false)
  const [draft, setDraft]       = useState(content)
  const [expanded, setExpanded] = useState(false)
  const [selBar, setSelBar]     = useState<SelectionBar | null>(null)
  const bodyRef = useRef<HTMLDivElement>(null)

  const isLong = content.split('\n').length > 6
  const preview = isLong && !expanded && !editing ? content.split('\n').slice(0, 6).join('\n') : content

  function commitEdit() {
    updateBodyCell(id, draft)
    setEditing(false)
  }

  const handleMouseUp = useCallback(() => {
    const sel = window.getSelection()
    if (!sel || sel.isCollapsed || !sel.toString().trim()) {
      setSelBar(null)
      return
    }
    const range = sel.getRangeAt(0)
    const rect  = range.getBoundingClientRect()
    const cRect = bodyRef.current?.getBoundingClientRect()
    if (!cRect) return
    setSelBar({
      x: rect.left + rect.width / 2 - cRect.left,
      y: rect.top - cRect.top - 4,
      text: sel.toString(),
    })
  }, [])

  function handleNewCellFromSelection() {
    if (!selBar) return
    const trimmed = selBar.text.trim()
    insertBodyCell('New section', trimmed, id)
    setSelBar(null)
    window.getSelection()?.removeAllRanges()
  }

  return (
    <div className={styles.cell}>
      <div className={styles.cellHead}>
        <span className={styles.title}>{heading}</span>
        <span className={styles.typeBadge}>body</span>
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.actionBtn}
            aria-label="Move up"
            title="Move up"
            disabled={isFirst}
            onClick={onMoveUp}
          >
            <ChevronUp size={12} />
          </button>
          <button
            type="button"
            className={styles.actionBtn}
            aria-label="Move down"
            title="Move down"
            disabled={isLast}
            onClick={onMoveDown}
          >
            <ChevronDown size={12} />
          </button>
          {!editing ? (
            <button
              type="button"
              className={styles.actionBtn}
              title="Edit"
              onClick={() => { setDraft(content); setEditing(true) }}
            >
              <Pencil size={12} />
            </button>
          ) : (
            <button
              type="button"
              className={`${styles.actionBtn} ${styles.actionBtnSave}`}
              title="Save (⌘Enter)"
              onClick={commitEdit}
            >
              <Check size={12} />
            </button>
          )}
          <Lock size={12} className={styles.lock} />
        </div>
      </div>

      <div className={styles.cellBody} ref={bodyRef} onMouseUp={handleMouseUp}>
        {editing ? (
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
              <button type="button" className={styles.toggle} onClick={() => setExpanded(e => !e)}>
                {expanded ? '▴ Collapse' : '▾ Show full content'}
              </button>
            )}
          </>
        )}

        {selBar && !editing && (
          <div
            className={styles.selBar}
            style={{ '--sel-x': `${selBar.x}px`, '--sel-y': `${selBar.y}px` } as React.CSSProperties}
            onMouseDown={e => e.preventDefault()}
          >
            <button type="button" className={styles.selBtn} onClick={handleNewCellFromSelection}>
              <Sparkles size={12} />
              <span>New cell from selection</span>
            </button>
            <span className={styles.selDivider} />
            <button type="button" className={styles.selBtnIcon} title="Insert as fragment" onClick={() => setSelBar(null)}>
              <Diamond size={12} />
            </button>
            <button type="button" className={styles.selBtnIcon} title="Code" onClick={() => setSelBar(null)}>
              <Code size={12} />
            </button>
            <button type="button" className={styles.selBtnIcon} title="Bold" onClick={() => setSelBar(null)}>
              <Bold size={12} />
            </button>
            <button type="button" className={styles.selBtnIcon} title="Italic" onClick={() => setSelBar(null)}>
              <Italic size={12} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
