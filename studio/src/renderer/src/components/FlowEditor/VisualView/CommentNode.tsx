import React, { useState } from 'react'
import type { NodeProps } from 'reactflow'
import { Handle, Position } from 'reactflow'
import { FileText, MessageCircle, Trash2 } from 'lucide-react'
import type { CommentEntry, CommentColor, CommentShape } from '../../../types'
import { Tooltip } from '../../ui'
import styles from './CommentNode.module.css'

interface CommentNodeData extends CommentEntry {
  onUpdate: (id: string, patch: Partial<Omit<CommentEntry, 'id'>>) => void
  onDelete: (id: string) => void
  states?: string[]
}

const ALL_COLORS: CommentColor[] = ['yellow', 'teal', 'red', 'purple', 'grey']

export function CommentNode({ data }: NodeProps<CommentNodeData>): JSX.Element {
  const [editing, setEditing] = useState(false)

  const nodeClass = [styles.node, data.shape === 'bubble' ? styles.bubble : ''].filter(Boolean).join(' ')

  function toggleShape(): void {
    const next: CommentShape = data.shape === 'sticky' ? 'bubble' : 'sticky'
    data.onUpdate(data.id, { shape: next })
  }

  function handleBlur(e: React.FocusEvent<HTMLTextAreaElement>): void {
    data.onUpdate(data.id, { text: e.currentTarget.value })
    setEditing(false)
  }

  return (
    <div
      className={nodeClass}
      data-color={data.color}
    >
      <div className={styles.toolbar}>
        <Tooltip label={data.shape === 'sticky' ? 'Switch to speech bubble' : 'Switch to sticky note'} placement="top">
          <button
            type="button"
            className={styles.shapeBtn}
            onClick={toggleShape}
            aria-label={data.shape === 'sticky' ? 'Switch to speech bubble' : 'Switch to sticky note'}
          >
            {data.shape === 'sticky' ? <FileText size={15} /> : <MessageCircle size={15} />}
          </button>
        </Tooltip>

        <div className={styles.swatches}>
          {ALL_COLORS.map((c) => (
            <Tooltip key={c} label={c} placement="top">
              <button
                type="button"
                className={[styles.swatch, data.color === c ? styles.swatchActive : ''].filter(Boolean).join(' ')}
                data-swatch={c}
                onClick={() => data.onUpdate(data.id, { color: c })}
                aria-label={`Set color ${c}`}
                {...(data.color === c ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
              />
            </Tooltip>
          ))}
        </div>

        {(data.states ?? []).length > 0 && (
          <select
            className={[styles.attachSelect, 'nodrag'].join(' ')}
            value={data.attachedTo ?? ''}
            onChange={(e) => data.onUpdate(data.id, { attachedTo: e.target.value || undefined })}
            aria-label="Link to state"
            title="Attach to state node"
          >
            <option value="">— link —</option>
            {(data.states ?? []).map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        )}

        <Tooltip label="Delete note" placement="top">
          <button
            type="button"
            className={styles.deleteBtn}
            onClick={() => data.onDelete(data.id)}
            aria-label="Delete comment"
          >
            <Trash2 size={12} />
          </button>
        </Tooltip>
      </div>

      {editing ? (
        <textarea
          className={[styles.textarea, 'nodrag'].join(' ')}
          defaultValue={data.text}
          autoFocus
          onBlur={handleBlur}
          aria-label="Comment text"
        />
      ) : (
        <div
          className={styles.textDisplay}
          role="textbox"
          tabIndex={0}
          aria-label="Comment text, click to edit"
          onClick={() => setEditing(true)}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setEditing(true) }}
        >
          {data.text ? data.text : <span className={styles.placeholder}>Click to add noteâ€¦</span>}
        </div>
      )}
      <Handle
        type="source"
        position={Position.Right}
        id="attach-src"
        className={styles.attachHandle}
      />
    </div>
  )
}
