import type { TransitionRule, ArtifactCondition } from '../types'
import styles from './Step7TransitionRules.module.css'

interface Step7TransitionRulesProps {
  nonTerminalStates: string[]
  validStates: string[]
  transitionRules: Record<string, TransitionRule>
  onSetRules: (rules: Record<string, TransitionRule>) => void
}

function emptyRule(defaultState: string): TransitionRule {
  return { conditions: [], default: defaultState }
}

export function Step7TransitionRules({
  nonTerminalStates,
  validStates,
  transitionRules,
  onSetRules,
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
    setRule(state, { ...rule, conditions: rule.conditions.filter((_, i: number) => i !== idx) })
  }

  function updateCondition(state: string, idx: number, patch: Partial<ArtifactCondition>): void {
    const rule = getRule(state)
    setRule(state, {
      ...rule,
      conditions: rule.conditions.map((c: ArtifactCondition, i: number) => i === idx ? { ...c, ...patch } : c),
    })
  }

  function updateDefault(state: string, defaultTarget: string): void {
    setRule(state, { ...getRule(state), default: defaultTarget })
  }

  return (
    <div className={styles.root}>
      <div className={styles.desc}>
        Example: if <code>REVIEW_FAILURES.md</code> exists when leaving REVIEWING, go back to BUILDING instead of TESTING.
      </div>

      {nonTerminalStates.map((state) => {
        const rule = getRule(state)
        return (
          <div key={state} className={styles.stateBlock}>
            <div className={styles.stateHeader}>
              <span className={styles.stateName}>{state}</span>
              <button type="button" className={styles.addBtn} onClick={() => addCondition(state)}>+ If artifact exists…</button>
            </div>

            {rule.conditions.map((cond: ArtifactCondition, idx: number) => (
              <div key={idx} className={styles.conditionRow}>
                <span className={styles.conditionLabel}>if</span>
                <input
                  className={styles.input}
                  type="text"
                  value={cond.artifact}
                  placeholder="REVIEW_FAILURES.md"
                  onChange={(e) => updateCondition(state, idx, { artifact: e.target.value })}
                />
                <span className={styles.conditionLabel}>→ go to</span>
                <select
                  className={styles.select}
                  aria-label="Target state"
                  value={cond.target}
                  onChange={(e) => updateCondition(state, idx, { target: e.target.value })}
                >
                  <option value="">— select state —</option>
                  {validStates.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <button type="button" className={styles.removeBtn} onClick={() => removeCondition(state, idx)} aria-label="Remove condition">×</button>
              </div>
            ))}

            <div className={styles.defaultRow}>
              <span className={styles.conditionLabel}>default →</span>
              <select
                className={styles.select}
                aria-label="Default target state"
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
        <div className={styles.emptyMsg}>No non-terminal states found. Define states in step 2 first.</div>
      )}
    </div>
  )
}
