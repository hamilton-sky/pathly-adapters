import React from 'react'
import type { Transition, Gate } from '../types'
import styles from './Step5Gates.module.css'

interface Step5GatesProps {
  transitions: Transition[]
  gates: Record<string, Gate[]>
  onSetGates: (gates: Record<string, Gate[]>) => void
}

const GATE_TYPES: Gate['type'][] = ['verify_gate', 'scope_gate', 'require_artifact']

const GATE_LABELS: Record<Gate['type'], string> = {
  verify_gate: 'Verify gate (checks a pass marker in a file)',
  scope_gate: 'Scope gate (checks scope file for violations)',
  require_artifact: 'Require artifact (file must exist)',
}

function gateKey(tr: Transition): string {
  return `${tr.from}->${tr.to}`
}

function defaultGate(type: Gate['type']): Gate {
  if (type === 'verify_gate') return { type, artifact: 'VERIFY.md', pass_marker: 'RESULT: PASS', on_fail: 'REVIEW_FAILURES.md' }
  if (type === 'scope_gate') return { type, scope_file: 'CONVERSATION_PROMPTS.md', on_fail: 'SCOPE_VIOLATION.md' }
  return { type: 'require_artifact', artifact: '', on_fail: 'HUMAN_QUESTIONS.md' }
}

export function Step5Gates({ transitions, gates, onSetGates }: Step5GatesProps): JSX.Element {
  function getGates(tr: Transition): Gate[] { return gates[gateKey(tr)] ?? [] }
  function setGatesForTransition(tr: Transition, newGates: Gate[]): void {
    const key = gateKey(tr)
    const next = { ...gates }
    if (newGates.length === 0) delete next[key]
    else next[key] = newGates
    onSetGates(next)
  }
  function addGate(tr: Transition): void { setGatesForTransition(tr, [...getGates(tr), defaultGate('verify_gate')]) }
  function removeGate(tr: Transition, idx: number): void { setGatesForTransition(tr, getGates(tr).filter((_, i) => i !== idx)) }
  function updateGate(tr: Transition, idx: number, patch: Partial<Gate>): void {
    setGatesForTransition(tr, getGates(tr).map((g, i) => i === idx ? { ...g, ...patch } : g))
  }
  function changeType(tr: Transition, idx: number, type: Gate['type']): void {
    setGatesForTransition(tr, getGates(tr).map((g, i) => i === idx ? defaultGate(type) : g))
  }

  return (
    <div className={styles.root}>
      <div className={styles.empty}>Step 5 / 8 - Optional quality checks on transitions</div>
      {transitions.length === 0 && <div className={styles.empty}>No transitions defined. Add transitions in step 3 first.</div>}
      {transitions.map((tr) => {
        const key = gateKey(tr)
        const trGates = getGates(tr)
        return (
          <div key={key} className={styles.card}>
            <div className={styles.header}>
              <span className={styles.state}>{tr.from} → {tr.to}</span>
              <button className="wizard-add-btn" onClick={() => addGate(tr)}>+ Add gate</button>
            </div>
            {trGates.length === 0 && <div className={styles.optional}>No gates — transition is always allowed</div>}
            {trGates.map((gate, idx) => (
              <div key={idx} className={styles.gateCard}>
                <div className={styles.gateHead}>
                  <select className={styles.select} style={{ width: 'auto', flex: 1, marginRight: '8px' }} value={gate.type} onChange={(e) => changeType(tr, idx, e.target.value as Gate['type'])}>
                    {GATE_TYPES.map((t) => <option key={t} value={t}>{GATE_LABELS[t]}</option>)}
                  </select>
                  <button className="wizard-remove-btn" onClick={() => removeGate(tr, idx)} aria-label="Remove gate">×</button>
                </div>
                {gate.type === 'verify_gate' && (
                  <div className={styles.stack}>
                    <label className={styles.label}>Artifact file</label>
                    <input className={styles.input} type="text" value={gate.artifact ?? ''} placeholder="VERIFY.md" onChange={(e) => updateGate(tr, idx, { artifact: e.target.value })} />
                    <label className={styles.label}>Pass marker (string to search for)</label>
                    <input className={styles.input} type="text" value={gate.pass_marker ?? ''} placeholder="RESULT: PASS" onChange={(e) => updateGate(tr, idx, { pass_marker: e.target.value })} />
                    <label className={styles.label}>On fail — write this file</label>
                    <input className={styles.input} type="text" value={gate.on_fail ?? ''} placeholder="REVIEW_FAILURES.md" onChange={(e) => updateGate(tr, idx, { on_fail: e.target.value })} />
                  </div>
                )}
                {gate.type === 'scope_gate' && (
                  <div className={styles.stack}>
                    <label className={styles.label}>Scope file</label>
                    <input className={styles.input} type="text" value={gate.scope_file ?? ''} placeholder="CONVERSATION_PROMPTS.md" onChange={(e) => updateGate(tr, idx, { scope_file: e.target.value })} />
                    <label className={styles.label}>On fail — write this file</label>
                    <input className={styles.input} type="text" value={gate.on_fail ?? ''} placeholder="SCOPE_VIOLATION.md" onChange={(e) => updateGate(tr, idx, { on_fail: e.target.value })} />
                  </div>
                )}
                {gate.type === 'require_artifact' && (
                  <div className={styles.stack}>
                    <label className={styles.label}>Required artifact</label>
                    <input className={styles.input} type="text" value={gate.artifact ?? ''} placeholder="REVIEW.md" onChange={(e) => updateGate(tr, idx, { artifact: e.target.value })} />
                    <label className={styles.label}>On fail — write this file</label>
                    <input className={styles.input} type="text" value={gate.on_fail ?? ''} placeholder="HUMAN_QUESTIONS.md" onChange={(e) => updateGate(tr, idx, { on_fail: e.target.value })} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}
