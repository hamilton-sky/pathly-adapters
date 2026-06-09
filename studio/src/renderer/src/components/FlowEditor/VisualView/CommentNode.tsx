import { useState } from 'react'
import type { NodeProps } from 'reactflow'
import { Handle, Position } from 'reactflow'
import { StickyNote, MessageSquare } from 'lucide-react'
import type { CommentEntry, CommentColor, CommentShape } from '../../../types'
import styles from './CommentNode.module.css'

interface CommentNodeData extends CommentEntry {
  onUpdate: (id: string, patch: Partial<Omit<CommentEntry, 'id'>>) => void
  onDelete: (id: string) => void
  states?: string[]
}

const COLOR_BG: Record<CommentColor, string> = {
  yellow: '#FEFCE8', teal: '#F0FDFA', red: '#FFF1F2', purple: '#FAF5FF', grey: '#F9FAFB',
}
const COLOR_BORDER: Record<CommentColor, string> = {
  yellow: '#FDE047', teal: '#5EEAD4', red: '#FDA4AF', purple: '#D8B4FE', grey: '#D1D5DB',
}
const COLOR_TEXT: Record<CommentColor, string> = {
  yellow: '#422006', teal: '#134E4A', red: '#881337', purple: '#581C87', grey: '#111827',
}

const SWATCH_COLORS: Record<CommentColor, string> = {
  yellow: '#FDE047', teal: '#5EEAD4', red: '#FDA4AF', purple: '#D8B4FE', grey: '#D1D5DB',
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
      style={{ '--cbg': COLOR_BG[data.color], '--cborder': COLOR_BORDER[data.color], '--ctext': COLOR_TEXT[data.color] } as React.CSSProperties}
    >
      <div className={styles.toolbar}>
        <button
          type="button"
          className={styles.shapeBtn}
          onClick={toggleShape}
          aria-label={data.shape === 'sticky' ? 'Switch to speech bubble' : 'Switch to sticky note'}
        >
          {data.shape === 'sticky' ? <StickyNote size={12} /> : <MessageSquare size={12} />}
        </button>

        <div className={styles.swatches}>
          {ALL_COLORS.map((c) => (
            <button
              key={c}
              type="button"
              className={[styles.swatch, data.color === c ? styles.swatchActive : ''].filter(Boolean).join(' ')}
              style={{ '--swatch-color': SWATCH_COLORS[c] } as React.CSSProperties}
              onClick={() => data.onUpdate(data.id, { color: c })}
              aria-label={`Set color ${c}`}
              aria-pressed={data.color === c}
            />
          ))}
        </div>

        {(data.states ?? []).length > 0 && (
          <select
            className={[styles.attachSelect, 'nodrag'].join(' ')}
            value={data.attachedTo ?? ''}
            onChange={(e) => data.onUpdate(data.id, { attachedTo: e.target.value || undefined })}
            aria-label="Link to state"
            title="Attach to state"
          >
            <option value="">— link —</option>
            {(data.states ?? []).map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        )}

        <button
          type="button"
          className={styles.deleteBtn}
          onClick={() => data.onDelete(data.id)}
          aria-label="Delete comment"
        >
          ×
        </button>
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
          {data.text ? data.text : <span className={styles.placeholder}>Click to add note…</span>}
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
