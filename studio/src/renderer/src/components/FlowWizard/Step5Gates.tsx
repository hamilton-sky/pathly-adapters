import React from 'react'
import type { Transition, Gate } from './types'

interface Step5GatesProps {
  transitions: Transition[]
  gates: Record<string, Gate[]>
  onSetGates: (gates: Record<string, Gate[]>) => void
  styles: Record<string, React.CSSProperties>
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

export function Step5Gates({ transitions, gates, onSetGates, styles }: Step5GatesProps): JSX.Element {
  function getGates(tr: Transition): Gate[] {
    return gates[gateKey(tr)] ?? []
  }

  function setGatesForTransition(tr: Transition, newGates: Gate[]): void {
    const key = gateKey(tr)
    const next = { ...gates }
    if (newGates.length === 0) {
      delete next[key]
    } else {
      next[key] = newGates
    }
    onSetGates(next)
  }

  function addGate(tr: Transition): void {
    setGatesForTransition(tr, [...getGates(tr), defaultGate('verify_gate')])
  }

  function removeGate(tr: Transition, idx: number): void {
    setGatesForTransition(tr, getGates(tr).filter((_, i) => i !== idx))
  }

  function updateGate(tr: Transition, idx: number, patch: Partial<Gate>): void {
    const next = getGates(tr).map((g, i) => i === idx ? { ...g, ...patch } : g)
    setGatesForTransition(tr, next)
  }

  function changeType(tr: Transition, idx: number, type: Gate['type']): void {
    const next = getGates(tr).map((g, i) => i === idx ? defaultGate(type) : g)
    setGatesForTransition(tr, next)
  }

  const inputStyle: React.CSSProperties = {
    backgroundColor: styles.input?.backgroundColor as string,
    border: styles.input?.border as string,
    borderRadius: '4px',
    color: styles.input?.color as string,
    fontSize: 'var(--font-size-sm)',
    padding: '4px 8px',
    outline: 'none',
    fontFamily: 'monospace',
    width: '100%',
    boxSizing: 'border-box',
  }

  const selectStyle: React.CSSProperties = { ...styles.select, fontSize: 'var(--font-size-sm)', width: '100%' }

  return (
    <div>
      <div style={styles.stepHeader}>Configure gates</div>
      <div style={styles.stepSub}>Step 5 / 8 — Optional quality checks on transitions</div>
      {transitions.length === 0 && (
        <div style={{ color: styles.stepSub?.color, fontSize: 'var(--font-size-sm)' }}>
          No transitions defined. Add transitions in step 3 first.
        </div>
      )}
      {transitions.map((tr) => {
        const key = gateKey(tr)
        const trGates = getGates(tr)
        return (
          <div key={key} style={{ marginBottom: '20px', padding: '12px', border: `1px solid`, borderColor: '#333', borderRadius: '6px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <span style={{ fontFamily: 'monospace', fontSize: 'var(--font-size-sm)', color: styles.stepHeader?.color }}>
                {tr.from} → {tr.to}
              </span>
              <button style={styles.addBtn} onClick={() => addGate(tr)}>+ Add gate</button>
            </div>
            {trGates.length === 0 && (
              <div style={{ color: styles.stepSub?.color, fontSize: '11px', fontStyle: 'italic' }}>No gates — transition is always allowed</div>
            )}
            {trGates.map((gate, idx) => (
              <div key={idx} style={{ marginBottom: '10px', padding: '10px', background: 'rgba(255,255,255,0.03)', borderRadius: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <select
                    style={{ ...selectStyle, width: 'auto', flex: 1, marginRight: '8px' }}
                    value={gate.type}
                    onChange={(e) => changeType(tr, idx, e.target.value as Gate['type'])}
                  >
                    {GATE_TYPES.map((t) => (
                      <option key={t} value={t}>{GATE_LABELS[t]}</option>
                    ))}
                  </select>
                  <button style={styles.removeBtn} onClick={() => removeGate(tr, idx)} aria-label="Remove gate">×</button>
                </div>
                {gate.type === 'verify_gate' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <label style={{ fontSize: '11px', color: styles.stepSub?.color }}>Artifact file</label>
                    <input style={inputStyle} type="text" value={gate.artifact ?? ''} placeholder="VERIFY.md" onChange={(e) => updateGate(tr, idx, { artifact: e.target.value })} />
                    <label style={{ fontSize: '11px', color: styles.stepSub?.color }}>Pass marker (string to search for)</label>
                    <input style={inputStyle} type="text" value={gate.pass_marker ?? ''} placeholder="RESULT: PASS" onChange={(e) => updateGate(tr, idx, { pass_marker: e.target.value })} />
                    <label style={{ fontSize: '11px', color: styles.stepSub?.color }}>On fail — write this file</label>
                    <input style={inputStyle} type="text" value={gate.on_fail ?? ''} placeholder="REVIEW_FAILURES.md" onChange={(e) => updateGate(tr, idx, { on_fail: e.target.value })} />
                  </div>
                )}
                {gate.type === 'scope_gate' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <label style={{ fontSize: '11px', color: styles.stepSub?.color }}>Scope file</label>
                    <input style={inputStyle} type="text" value={gate.scope_file ?? ''} placeholder="CONVERSATION_PROMPTS.md" onChange={(e) => updateGate(tr, idx, { scope_file: e.target.value })} />
                    <label style={{ fontSize: '11px', color: styles.stepSub?.color }}>On fail — write this file</label>
                    <input style={inputStyle} type="text" value={gate.on_fail ?? ''} placeholder="SCOPE_VIOLATION.md" onChange={(e) => updateGate(tr, idx, { on_fail: e.target.value })} />
                  </div>
                )}
                {gate.type === 'require_artifact' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <label style={{ fontSize: '11px', color: styles.stepSub?.color }}>Required artifact</label>
                    <input style={inputStyle} type="text" value={gate.artifact ?? ''} placeholder="REVIEW.md" onChange={(e) => updateGate(tr, idx, { artifact: e.target.value })} />
                    <label style={{ fontSize: '11px', color: styles.stepSub?.color }}>On fail — write this file</label>
                    <input style={inputStyle} type="text" value={gate.on_fail ?? ''} placeholder="HUMAN_QUESTIONS.md" onChange={(e) => updateGate(tr, idx, { on_fail: e.target.value })} />
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
