import React from 'react'

interface Step2StatesProps {
  states: string[]
  onUpdateState: (idx: number, value: string) => void
  onRemoveState: (idx: number) => void
  onAddState: () => void
  styles: Record<string, React.CSSProperties>
}

export function Step2States({
  states,
  onUpdateState,
  onRemoveState,
  onAddState,
  styles
}: Step2StatesProps): JSX.Element {
  return (
    <div>
      <div style={styles.stepHeader}>Define states</div>
      <div style={styles.stepSub}>Step 2 / 5 — First = initial, last = terminal</div>
      {states.map((state, idx) => (
        <div key={idx} style={styles.stateRow}>
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
    </div>
  )
}
