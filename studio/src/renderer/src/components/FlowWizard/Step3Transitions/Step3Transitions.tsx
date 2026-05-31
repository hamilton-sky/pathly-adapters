import styles from './Step3Transitions.module.css'
import type { Transition } from '../types'

interface Step3TransitionsProps {
  transitions: Transition[]
  validStates: string[]
  onUpdateTransition: (idx: number, patch: Partial<Transition>) => void
  onRemoveTransition: (idx: number) => void
  onAddTransition: () => void
}

export function Step3Transitions({
  transitions,
  validStates,
  onUpdateTransition,
  onRemoveTransition,
  onAddTransition,
}: Step3TransitionsProps): JSX.Element {
  return (
    <div className={styles.root}>
      <div className={styles.title}>Define transitions</div>
      <div className={styles.sub}>Step 3 / 8</div>
      {transitions.map((tr, idx) => (
        <div key={idx} className={styles.row}>
          <select
            className={styles.select}
            value={tr.from}
            aria-label="From state"
            onChange={(e) => onUpdateTransition(idx, { from: e.target.value })}
          >
            {validStates.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <span className={styles.arrow}>→</span>
          <select
            className={styles.select}
            value={tr.to}
            aria-label="To state"
            onChange={(e) => onUpdateTransition(idx, { to: e.target.value })}
          >
            {validStates.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <input
            className={styles.labelInput}
            type="text"
            value={tr.label}
            onChange={(e) => onUpdateTransition(idx, { label: e.target.value })}
            placeholder="label"
          />
          <button
            type="button"
            className={styles.removeBtn}
            onClick={() => onRemoveTransition(idx)}
            aria-label="Remove transition"
          >
            ×
          </button>
        </div>
      ))}
      <button type="button" className={styles.addBtn} onClick={onAddTransition}>+ Add transition</button>
    </div>
  )
}
