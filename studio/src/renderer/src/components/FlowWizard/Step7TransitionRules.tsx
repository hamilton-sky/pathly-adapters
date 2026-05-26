import React from 'react'
import type { TransitionRule, ArtifactCondition } from './types'

interface Step7TransitionRulesProps {
  nonTerminalStates: string[]
  validStates: string[]
  transitionRules: Record<string, TransitionRule>
  onSetRules: (rules: Record<string, TransitionRule>) => void
  styles: Record<string, React.CSSProperties>
}

function emptyRule(defaultState: string): TransitionRule {
  return { conditions: [], default: defaultState }
}

export function Step7TransitionRules({
  nonTerminalStates,
  validStates,
  transitionRules,
  onSetRules,
  styles,
}: Step7TransitionRulesProps): JSX.Element {
  function getRule(state: string): TransitionRule {
    return transitionRules[state] ?? emptyRule('')
  }

  function setRule(state: string, rule: TransitionRule): void {
    onSetRules({ ...transitionRules, [state]: rule })
  }

  function addCondition(state: string): void {
    const rule = getRule(state)
    setRule(state, {
      ...rule,
      conditions: [...rule.conditions, { artifact: '', target: '' }],
    })
  }

  function removeCondition(state: string, idx: number): void {
    const rule = getRule(state)
    setRule(state, { ...rule, conditions: rule.conditions.filter((_, i) => i !== idx) })
  }

  function updateCondition(state: string, idx: number, patch: Partial<ArtifactCondition>): void {
    const rule = getRule(state)
    setRule(state, {
      ...rule,
      conditions: rule.conditions.map((c, i) => i === idx ? { ...c, ...patch } : c),
    })
  }

  function updateDefault(state: string, defaultTarget: string): void {
    setRule(state, { ...getRule(state), default: defaultTarget })
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
    flex: 1,
  }

  const selectStyle: React.CSSProperties = { ...styles.select }

  return (
    <div>
      <div style={styles.stepHeader}>Transition rules</div>
      <div style={styles.stepSub}>Step 7 / 8 — Conditional routing based on artifact presence</div>

      <div style={{ marginBottom: '12px', fontSize: 'var(--font-size-sm)', color: styles.stepSub?.color }}>
        Example: if <code>REVIEW_FAILURES.md</code> exists when leaving REVIEWING, go back to BUILDING instead of TESTING.
      </div>

      {nonTerminalStates.map((state) => {
        const rule = getRule(state)
        return (
          <div key={state} style={{ marginBottom: '20px', padding: '12px', border: '1px solid #333', borderRadius: '6px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <span style={{ fontFamily: 'monospace', fontSize: 'var(--font-size-sm)', color: styles.stepHeader?.color }}>
                {state}
              </span>
              <button style={styles.addBtn} onClick={() => addCondition(state)}>+ If artifact exists…</button>
            </div>

            {rule.conditions.map((cond, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <span style={{ fontSize: '11px', color: styles.stepSub?.color, flexShrink: 0 }}>if</span>
                <input
                  style={inputStyle}
                  type="text"
                  value={cond.artifact}
                  placeholder="REVIEW_FAILURES.md"
                  onChange={(e) => updateCondition(state, idx, { artifact: e.target.value })}
                />
                <span style={{ fontSize: '11px', color: styles.stepSub?.color, flexShrink: 0 }}>→ go to</span>
                <select
                  style={{ ...selectStyle, flex: 1 }}
                  value={cond.target}
                  onChange={(e) => updateCondition(state, idx, { target: e.target.value })}
                >
                  <option value="">— select state —</option>
                  {validStates.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <button style={styles.removeBtn} onClick={() => removeCondition(state, idx)} aria-label="Remove condition">×</button>
              </div>
            ))}

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px' }}>
              <span style={{ fontSize: '11px', color: styles.stepSub?.color, flexShrink: 0 }}>default →</span>
              <select
                style={{ ...selectStyle, flex: 1 }}
                value={rule.default}
                onChange={(e) => updateDefault(state, e.target.value)}
              >
                <option value="">— no default (use transitions) —</option>
                {validStates.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          </div>
        )
      })}

      {nonTerminalStates.length === 0 && (
        <div style={{ color: styles.stepSub?.color, fontSize: 'var(--font-size-sm)' }}>
          No non-terminal states found. Define states in step 2 first.
        </div>
      )}
    </div>
  )
}
