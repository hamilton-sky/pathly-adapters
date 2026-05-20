import React from 'react'
import type { Transition } from './types'

interface Step3TransitionsProps {
  transitions: Transition[]
  validStates: string[]
  onUpdateTransition: (idx: number, patch: Partial<Transition>) => void
  onRemoveTransition: (idx: number) => void
  onAddTransition: () => void
  styles: Record<string, React.CSSProperties>
}

export function Step3Transitions({
  transitions,
  validStates,
  onUpdateTransition,
  onRemoveTransition,
  onAddTransition,
  styles
}: Step3TransitionsProps): JSX.Element {
  return (
    <div>
      <div style={styles.stepHeader}>Define transitions</div>
      <div style={styles.stepSub}>Step 3 / 5</div>
      {transitions.map((tr, idx) => (
        <div key={idx} style={styles.transitionRow}>
          <select
            style={styles.select}
            value={tr.from}
            aria-label="From state"
            onChange={(e) => onUpdateTransition(idx, { from: e.target.value })}
          >
            {validStates.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <span style={styles.transitionArrow}>→</span>
          <select
            style={styles.select}
            value={tr.to}
            aria-label="To state"
            onChange={(e) => onUpdateTransition(idx, { to: e.target.value })}
          >
            {validStates.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <input
            style={styles.transitionLabelInput}
            type="text"
            value={tr.label}
            onChange={(e) => onUpdateTransition(idx, { label: e.target.value })}
            placeholder="label"
          />
          <button
            style={styles.removeBtn}
            onClick={() => onRemoveTransition(idx)}
            aria-label="Remove transition"
          >
            ×
          </button>
        </div>
      ))}
      <button style={styles.addBtn} onClick={onAddTransition}>+ Add transition</button>
    </div>
  )
}
