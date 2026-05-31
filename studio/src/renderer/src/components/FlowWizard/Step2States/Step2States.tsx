import React from 'react'
import styles from './Step2States.module.css'

interface Step2StatesProps {
  states: string[]
  onUpdateState: (idx: number, value: string) => void
  onRemoveState: (idx: number) => void
  onAddState: () => void
  onReorderState: (from: number, to: number) => void
}

export function Step2States({
  states,
  onUpdateState,
  onRemoveState,
  onAddState,
  onReorderState,
}: Step2StatesProps): JSX.Element {
  return (
    <div className={styles.root}>
      <div className={styles.title}>Define stages</div>
      <div className={styles.sub}>Step 2 / 5 - Drag to reorder. Initial = first, terminal = last.</div>

      {states.map((state, idx) => (
        <div
          key={idx}
          className={styles.row}
          draggable
          onDragStart={(e) => {
            e.dataTransfer.setData('text/plain', String(idx))
            e.dataTransfer.effectAllowed = 'move'
          }}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault()
            const from = Number(e.dataTransfer.getData('text/plain'))
            if (!Number.isNaN(from)) onReorderState(from, idx)
          }}
        >
          <span className={styles.drag}>⋮⋮</span>
          <input
            id={`state-${idx}`}
            className={styles.input}
            type="text"
            value={state}
            onChange={(e) => onUpdateState(idx, e.target.value)}
            placeholder="STATE_NAME"
          />
          {idx === 0 && <span className={styles.tag}>initial</span>}
          {idx === states.length - 1 && <span className={styles.tag}>terminal</span>}
          <button
            className={styles.remove}
            onClick={() => onRemoveState(idx)}
            disabled={states.length <= 2}
            aria-label="Remove state"
          >
            ×
          </button>
        </div>
      ))}

      <button className={styles.add} onClick={onAddState}>+ Add state</button>

      <div className={styles.previewLabel}>Pipeline preview</div>
      <div className={styles.previewBox}>
        {states.map((item, idx) => (
          <React.Fragment key={idx}>
            <span className={`${styles.pill} ${idx === states.length - 1 ? styles.pillTerm : ''}`}>
              {item || 'STATE'}
            </span>
            {idx < states.length - 1 && <span className={styles.arrow}>→</span>}
          </React.Fragment>
        ))}
      </div>
    </div>
  )
}
