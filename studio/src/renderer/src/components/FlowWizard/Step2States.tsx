import React from 'react'

interface Step2StatesProps {
  states: string[]
  onUpdateState: (idx: number, value: string) => void
  onRemoveState: (idx: number) => void
  onAddState: () => void
  onReorderState: (from: number, to: number) => void
  styles: Record<string, React.CSSProperties>
}

export function Step2States({
  states,
  onUpdateState,
  onRemoveState,
  onAddState,
  onReorderState,
  styles
}: Step2StatesProps): JSX.Element {
  return (
    <div>
      <div style={styles.stepHeader}>Define stages</div>
      <div style={styles.stepSub}>Step 2 / 5 - Drag to reorder. Initial = first, terminal = last.</div>

      {states.map((state, idx) => (
        <div
          key={`${state}-${idx}`}
          style={styles.stateRow}
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
          <span style={{ ...styles.stateTag, cursor: 'grab', userSelect: 'none' }}>⋮⋮</span>
          <input
            id={`state-${idx}`}
            style={styles.stateInput}
            type="text"
            value={state}
            onChange={(e) => onUpdateState(idx, e.target.value)}
            placeholder="STATE_NAME"
          />
          {idx === 0 && <span style={styles.stateTag}>initial</span>}
          {idx === states.length - 1 && <span style={styles.stateTag}>terminal</span>}
          <button
            style={styles.removeBtn}
            onClick={() => onRemoveState(idx)}
            disabled={states.length <= 2}
            aria-label="Remove state"
          >
            ×
          </button>
        </div>
      ))}

      <button style={styles.addBtn} onClick={onAddState}>+ Add state</button>

      <div style={{ marginTop: '18px' }}>
        <div style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '0.08em', color: styles.stepSub.color, marginBottom: '8px' }}>
          Pipeline preview
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '6px', padding: '10px 12px', backgroundColor: styles.input.backgroundColor as string, border: styles.input.border as string, borderRadius: '6px' }}>
          {states.map((item, idx) => (
            <React.Fragment key={`${item}-${idx}`}>
              <span
                style={{
                  fontSize: '11px',
                  fontFamily: 'monospace',
                  color: idx === states.length - 1 ? styles.stepHeader.color : styles.stepHeader.color,
                  backgroundColor: idx === states.length - 1 ? 'rgba(166,227,161,0.12)' : 'rgba(137,180,250,0.12)',
                  border: `1px solid ${idx === states.length - 1 ? 'rgba(166,227,161,0.25)' : 'rgba(137,180,250,0.25)'}`,
                  borderRadius: '20px',
                  padding: '3px 8px',
                  maxWidth: '110px',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap'
                }}
              >
                {item || 'STATE'}
              </span>
              {idx < states.length - 1 && <span style={{ color: styles.stepSub.color }}>→</span>}
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
  )
}
