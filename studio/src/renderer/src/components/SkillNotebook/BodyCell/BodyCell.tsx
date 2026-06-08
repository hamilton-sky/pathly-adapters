import React, { useState } from 'react'
import { Lock, Pencil, Check } from 'lucide-react'
import MarkdownRenderer from '../../shared/MarkdownRenderer/MarkdownRenderer'
import { useSkillNotebookStore } from '../../../store/skillNotebookStore'
import styles from './BodyCell.module.css'

interface Props {
  id: string
  heading: string
  content: string
}

export default function BodyCell({ id, heading, content }: Props) {
  const updateBodyCell = useSkillNotebookStore(s => s.updateBodyCell)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(content)
  const [expanded, setExpanded] = useState(false)

  const isLong = content.split('\n').length > 6
  const preview = isLong && !expanded && !editing ? content.split('\n').slice(0, 6).join('\n') : content

  function commitEdit() {
    updateBodyCell(id, draft)
    setEditing(false)
  }

  return (
    <div className={styles.cell}>
      <div className={styles.cellHead}>
        <span className={styles.title}>{heading}</span>
        <span className={styles.typeBadge}>body</span>
        <div className={styles.actions}>
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
              title="Save"
              onClick={commitEdit}
            >
              <Check size={12} />
            </button>
          )}
          <Lock size={12} className={styles.lock} />
        </div>
      </div>
      <div className={styles.cellBody}>
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
      </div>
    </div>
  )
}
