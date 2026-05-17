import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { useTheme } from '../useTheme'
import type { Theme } from '../theme'

interface Props {
  onClose: () => void
  onCreated: (filePath: string) => void
}

interface Transition {
  from: string
  to: string
  label: string
}

function makeStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    overlay: {
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(0,0,0,0.7)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    },
    card: {
      width: '600px',
      maxHeight: '80vh',
      backgroundColor: t.bgMantle,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '8px',
      display: 'flex',
      flexDirection: 'column'
    },
    stepIndicator: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '8px',
      padding: '16px 24px',
      borderBottom: `1px solid ${t.bgSurface0}`,
      flexShrink: 0
    },
    stepDot: (active: boolean, done: boolean): React.CSSProperties => ({
      width: '28px',
      height: '28px',
      borderRadius: '50%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: '13px',
      fontWeight: 600,
      backgroundColor: done ? t.green : active ? t.accent : t.bgSurface0,
      color: done || active ? t.bgBase : t.textMuted,
      flexShrink: 0
    }),
    stepConnector: {
      flex: 1,
      height: '1px',
      backgroundColor: t.bgSurface0,
      maxWidth: '40px'
    },
    content: {
      flex: 1,
      overflowY: 'auto',
      padding: '24px'
    },
    stepHeader: {
      fontSize: '16px',
      fontWeight: 600,
      color: t.textPrimary,
      marginBottom: '4px'
    },
    stepSub: {
      fontSize: '12px',
      color: t.textMuted,
      marginBottom: '20px'
    },
    label: {
      display: 'block',
      fontSize: '12px',
      color: t.textSecondary,
      marginBottom: '6px',
      fontWeight: 600
    },
    input: {
      width: '100%',
      boxSizing: 'border-box' as const,
      backgroundColor: t.bgBase,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: '13px',
      padding: '8px 10px',
      outline: 'none',
      marginBottom: '16px',
      fontFamily: 'inherit'
    },
    textarea: {
      width: '100%',
      boxSizing: 'border-box' as const,
      backgroundColor: t.bgBase,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: '13px',
      padding: '8px 10px',
      outline: 'none',
      marginBottom: '16px',
      resize: 'vertical' as const,
      minHeight: '80px',
      fontFamily: 'inherit'
    },
    stateRow: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      marginBottom: '8px'
    },
    stateInput: {
      flex: 1,
      backgroundColor: t.bgBase,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: '13px',
      padding: '6px 10px',
      outline: 'none',
      fontFamily: 'monospace'
    },
    removeBtn: {
      background: 'none',
      border: 'none',
      color: t.textMuted,
      cursor: 'pointer',
      fontSize: '16px',
      padding: '0 4px',
      lineHeight: 1,
      flexShrink: 0
    },
    addBtn: {
      background: 'none',
      border: `1px dashed ${t.bgSurface1}`,
      borderRadius: '4px',
      color: t.blue,
      cursor: 'pointer',
      fontSize: '12px',
      padding: '6px 12px',
      marginTop: '4px'
    },
    stateTag: {
      fontSize: '11px',
      color: t.textMuted,
      flexShrink: 0
    },
    transitionRow: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      marginBottom: '8px'
    },
    select: {
      backgroundColor: t.bgBase,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: '12px',
      padding: '5px 8px',
      outline: 'none',
      cursor: 'pointer'
    },
    transitionArrow: {
      color: t.textMuted,
      flexShrink: 0
    },
    transitionLabelInput: {
      width: '100px',
      backgroundColor: t.bgBase,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: '12px',
      padding: '5px 8px',
      outline: 'none'
    },
    agentRow: {
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      marginBottom: '10px'
    },
    agentStateName: {
      width: '120px',
      fontSize: '12px',
      color: t.textSecondary,
      fontFamily: 'monospace',
      flexShrink: 0
    },
    agentInput: {
      flex: 1,
      backgroundColor: t.bgBase,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: '12px',
      padding: '5px 8px',
      outline: 'none',
      fontFamily: 'monospace'
    },
    terminalNote: {
      fontSize: '12px',
      color: t.textMuted,
      fontStyle: 'italic'
    },
    preBlock: {
      backgroundColor: t.bgBase,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '4px',
      padding: '12px',
      fontSize: '12px',
      fontFamily: 'monospace',
      color: t.textPrimary,
      overflowX: 'auto',
      whiteSpace: 'pre' as const,
      maxHeight: '240px',
      overflowY: 'auto'
    },
    storageRow: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      marginTop: '16px'
    },
    storageLabel: {
      fontSize: '12px',
      color: t.textSecondary,
      flexShrink: 0
    },
    storageInput: {
      flex: 1,
      backgroundColor: t.bgBase,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: '12px',
      padding: '5px 8px',
      outline: 'none',
      fontFamily: 'monospace'
    },
    btnRow: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '16px 24px',
      borderTop: `1px solid ${t.bgSurface0}`,
      flexShrink: 0
    },
    backBtn: {
      background: 'none',
      border: `1px solid ${t.bgSurface1}`,
      borderRadius: '4px',
      color: t.textSecondary,
      cursor: 'pointer',
      padding: '6px 16px',
      fontSize: '13px'
    },
    nextBtn: {
      background: t.accent,
      border: 'none',
      borderRadius: '4px',
      color: t.bgBase,
      cursor: 'pointer',
      padding: '6px 16px',
      fontSize: '13px',
      fontWeight: 600
    },
    cancelBtn: {
      background: 'none',
      border: 'none',
      color: t.textMuted,
      cursor: 'pointer',
      padding: '6px 10px',
      fontSize: '13px'
    },
    error: {
      color: t.red,
      fontSize: '12px',
      marginTop: '4px'
    }
  }
}

function generateYaml(
  flowName: string,
  storagePath: string,
  states: string[],
  agentMap: Record<string, string>,
  transitions: Transition[]
): string {
  // Build plain target-list map (matches FlowYaml: Record<string, string[]>)
  const transitionMap: Record<string, string[]> = {}
  for (const tr of transitions) {
    if (!transitionMap[tr.from]) transitionMap[tr.from] = []
    if (!transitionMap[tr.from].includes(tr.to)) {
      transitionMap[tr.from].push(tr.to)
    }
  }

  const lines: string[] = [
    `version: 1`,
    `flow: ${flowName}`,
    `storage_path: "${storagePath}"`,
    ``,
    `states:`
  ]
  for (const s of states) {
    lines.push(`  - ${s}`)
  }
  lines.push(``)
  lines.push(`agent_map:`)
  for (const s of states) {
    if (agentMap[s]) {
      lines.push(`  ${s}: ${agentMap[s]}`)
    }
  }
  lines.push(``)
  lines.push(`transitions:`)
  for (const s of states) {
    const targets = transitionMap[s]
    if (targets && targets.length > 0) {
      lines.push(`  ${s}:`)
      for (const target of targets) {
        lines.push(`    - ${target}`)      // plain string list, not label:target objects
      }
    }
  }

  return lines.join('\n')
}

export function FlowWizard({ onClose, onCreated }: Props): JSX.Element {
  const { projectPath } = useStore()
  const t = useTheme()
  const styles = makeStyles(t)

  const [step, setStep] = useState(1)
  const [flowName, setFlowName] = useState('')
  const [description, setDescription] = useState('')
  const [states, setStates] = useState(['STORMING', 'PLANNING', 'BUILDING', 'REVIEWING', 'TESTING', 'DONE'])
  const [transitions, setTransitions] = useState<Transition[]>([])
  const [agentMap, setAgentMap] = useState<Record<string, string>>({})
  const [storagePath, setStoragePath] = useState('pathly/plans/{topic}/')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent): void {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  function goToStep(next: number): void {
    if (next === 3 && step === 2) {
      const autoTransitions: Transition[] = []
      for (let i = 0; i < states.length - 1; i++) {
        autoTransitions.push({ from: states[i], to: states[i + 1], label: 'default' })
      }
      if (transitions.length === 0) {
        setTransitions(autoTransitions)
      }
    }
    setError(null)
    setStep(next)
  }

  function handleNext(): void {
    if (step === 1) {
      if (!flowName.trim()) {
        setError('Flow name is required')
        return
      }
      if (!/^[a-zA-Z0-9-_]+$/.test(flowName.trim())) {
        setError('Flow name must be alphanumeric with hyphens or underscores')
        return
      }
    }
    if (step === 2) {
      const nonEmpty = states.filter((s) => s.trim())
      if (nonEmpty.length < 2) {
        setError('At least 2 states required')
        return
      }
    }
    goToStep(step + 1)
  }

  function handleBack(): void {
    setError(null)
    setStep((s) => s - 1)
  }

  function updateState(idx: number, value: string): void {
    const next = [...states]
    next[idx] = value.toUpperCase()
    setStates(next)
  }

  function removeState(idx: number): void {
    if (states.length <= 2) return
    setStates((s) => s.filter((_, i) => i !== idx))
  }

  function addState(): void {
    setStates((s) => [...s, ''])
  }

  function updateTransition(idx: number, patch: Partial<Transition>): void {
    setTransitions((prev) => prev.map((tr, i) => (i === idx ? { ...tr, ...patch } : tr)))
  }

  function removeTransition(idx: number): void {
    setTransitions((prev) => prev.filter((_, i) => i !== idx))
  }

  function addTransition(): void {
    setTransitions((prev) => [...prev, { from: states[0] ?? '', to: states[1] ?? '', label: 'default' }])
  }

  function updateAgent(state: string, value: string): void {
    setAgentMap((prev) => ({ ...prev, [state]: value }))
  }

  async function handleSave(): Promise<void> {
    if (!projectPath) return
    const trimmedName = flowName.trim()
    const yaml = generateYaml(trimmedName, storagePath, states.filter((s) => s.trim()), agentMap, transitions)
    const filePath = `${projectPath}/src/pathly_data/core/flows/${trimmedName}.flow.yaml`
    try {
      await window.pathly.fs.write(filePath, yaml)
      onCreated(filePath)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const nonTerminalStates = states.slice(0, -1)
  const terminalState = states[states.length - 1]
  const validStates = states.filter((s) => s.trim())

  const yamlPreview = generateYaml(
    flowName || 'my-flow',
    storagePath,
    validStates,
    agentMap,
    transitions
  )

  return (
    <div style={styles.overlay} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div style={styles.card}>
        <div style={styles.stepIndicator}>
          {[1, 2, 3, 4, 5].map((n, i) => (
            <>
              <div
                key={n}
                style={typeof styles.stepDot === 'function'
                  ? styles.stepDot(step === n, step > n)
                  : {}}
              >
                {step > n ? '✓' : n}
              </div>
              {i < 4 && <div style={styles.stepConnector} />}
            </>
          ))}
        </div>

        <div style={styles.content}>
          {step === 1 && (
            <div>
              <div style={styles.stepHeader}>Create a new flow</div>
              <div style={styles.stepSub}>Step 1 / 5 — Name & Description</div>
              <label style={styles.label}>Flow name *</label>
              <input
                style={styles.input}
                type="text"
                placeholder="my-flow"
                value={flowName}
                onChange={(e) => setFlowName(e.target.value)}
              />
              <label style={styles.label}>Description (optional)</label>
              <textarea
                style={styles.textarea}
                placeholder="Describe this flow…"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
              {error && <div style={styles.error}>{error}</div>}
            </div>
          )}

          {step === 2 && (
            <div>
              <div style={styles.stepHeader}>Define states</div>
              <div style={styles.stepSub}>Step 2 / 5 — First = initial, last = terminal</div>
              {states.map((state, idx) => (
                <div key={idx} style={styles.stateRow}>
                  <input
                    style={styles.stateInput}
                    type="text"
                    value={state}
                    onChange={(e) => updateState(idx, e.target.value)}
                    placeholder="STATE_NAME"
                  />
                  {idx === 0 && <span style={styles.stateTag}>initial</span>}
                  {idx === states.length - 1 && <span style={styles.stateTag}>terminal</span>}
                  <button
                    style={styles.removeBtn}
                    onClick={() => removeState(idx)}
                    disabled={states.length <= 2}
                    title="Remove state"
                  >
                    ×
                  </button>
                </div>
              ))}
              <button style={styles.addBtn} onClick={addState}>+ Add state</button>
              {error && <div style={styles.error}>{error}</div>}
            </div>
          )}

          {step === 3 && (
            <div>
              <div style={styles.stepHeader}>Define transitions</div>
              <div style={styles.stepSub}>Step 3 / 5</div>
              {transitions.map((tr, idx) => (
                <div key={idx} style={styles.transitionRow}>
                  <select
                    style={styles.select}
                    value={tr.from}
                    onChange={(e) => updateTransition(idx, { from: e.target.value })}
                  >
                    {validStates.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                  <span style={styles.transitionArrow}>→</span>
                  <select
                    style={styles.select}
                    value={tr.to}
                    onChange={(e) => updateTransition(idx, { to: e.target.value })}
                  >
                    {validStates.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                  <input
                    style={styles.transitionLabelInput}
                    type="text"
                    value={tr.label}
                    onChange={(e) => updateTransition(idx, { label: e.target.value })}
                    placeholder="label"
                  />
                  <button style={styles.removeBtn} onClick={() => removeTransition(idx)}>×</button>
                </div>
              ))}
              <button style={styles.addBtn} onClick={addTransition}>+ Add transition</button>
            </div>
          )}

          {step === 4 && (
            <div>
              <div style={styles.stepHeader}>Assign agents</div>
              <div style={styles.stepSub}>Step 4 / 5 — Map agents to non-terminal states</div>
              {nonTerminalStates.filter((s) => s.trim()).map((state) => (
                <div key={state} style={styles.agentRow}>
                  <span style={styles.agentStateName}>{state}</span>
                  <input
                    style={styles.agentInput}
                    type="text"
                    placeholder="team/build"
                    value={agentMap[state] ?? ''}
                    onChange={(e) => updateAgent(state, e.target.value)}
                  />
                </div>
              ))}
              {terminalState && terminalState.trim() && (
                <div style={styles.agentRow}>
                  <span style={styles.agentStateName}>{terminalState}</span>
                  <span style={styles.terminalNote}>— (terminal, no agent)</span>
                </div>
              )}
            </div>
          )}

          {step === 5 && (
            <div>
              <div style={styles.stepHeader}>Review & Save</div>
              <div style={styles.stepSub}>Step 5 / 5 — Review the generated YAML</div>
              <pre style={styles.preBlock}>{yamlPreview}</pre>
              <div style={styles.storageRow}>
                <span style={styles.storageLabel}>Storage path:</span>
                <input
                  style={styles.storageInput}
                  type="text"
                  value={storagePath}
                  onChange={(e) => setStoragePath(e.target.value)}
                />
              </div>
              {error && <div style={styles.error}>{error}</div>}
            </div>
          )}
        </div>

        <div style={styles.btnRow}>
          <button style={styles.cancelBtn} onClick={onClose}>Cancel</button>
          <div style={{ display: 'flex', gap: '8px' }}>
            {step > 1 && (
              <button style={styles.backBtn} onClick={handleBack}>← Back</button>
            )}
            {step < 5 ? (
              <button style={styles.nextBtn} onClick={handleNext}>Next →</button>
            ) : (
              <button style={styles.nextBtn} onClick={handleSave}>Save Flow</button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
