import React from 'react'
import type { FeedbackRoute } from './types'

interface Step6FeedbackRoutingProps {
  feedbackRoutes: FeedbackRoute[]
  onSetRoutes: (routes: FeedbackRoute[]) => void
  styles: Record<string, React.CSSProperties>
}

const COMMON_TAGS = [
  'HUMAN_QUESTIONS',
  'BLOCKED_ON_HUMAN',
  'ARCH_FEEDBACK',
  'DESIGN_QUESTIONS',
  'IMPL_QUESTIONS',
  'REVIEW_FAILURES',
  'SCOPE_VIOLATION',
  'TEST_FAILURES',
]

export function Step6FeedbackRouting({ feedbackRoutes, onSetRoutes, styles }: Step6FeedbackRoutingProps): JSX.Element {
  function updateRoute(idx: number, patch: Partial<FeedbackRoute>): void {
    onSetRoutes(feedbackRoutes.map((r, i) => i === idx ? { ...r, ...patch } : r))
  }

  function removeRoute(idx: number): void {
    onSetRoutes(feedbackRoutes.filter((_, i) => i !== idx))
  }

  function addRoute(): void {
    onSetRoutes([...feedbackRoutes, { tag: '', agent: '' }])
  }

  const usedTags = new Set(feedbackRoutes.map((r) => r.tag))
  const unusedCommon = COMMON_TAGS.filter((t) => !usedTags.has(t))

  const inputStyle: React.CSSProperties = {
    backgroundColor: styles.input?.backgroundColor as string,
    border: styles.input?.border as string,
    borderRadius: '4px',
    color: styles.input?.color as string,
    fontSize: 'var(--font-size-sm)',
    padding: '5px 8px',
    outline: 'none',
    fontFamily: 'monospace',
    flex: 1,
  }

  return (
    <div>
      <div style={styles.stepHeader}>Feedback routing</div>
      <div style={styles.stepSub}>Step 6 / 8 — Map feedback tags to agents that handle them</div>

      <div style={{ marginBottom: '12px', fontSize: 'var(--font-size-sm)', color: styles.stepSub?.color }}>
        When an agent writes a feedback file (e.g. <code>REVIEW_FAILURES.md</code>), the FSM routes it to the mapped agent.
      </div>

      {feedbackRoutes.map((route, idx) => (
        <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
          <input
            style={{ ...inputStyle, fontFamily: 'monospace' }}
            type="text"
            list={`tag-suggestions-${idx}`}
            value={route.tag}
            placeholder="REVIEW_FAILURES"
            onChange={(e) => updateRoute(idx, { tag: e.target.value.toUpperCase() })}
          />
          <datalist id={`tag-suggestions-${idx}`}>
            {COMMON_TAGS.map((t) => <option key={t} value={t} />)}
          </datalist>
          <span style={{ color: styles.stepSub?.color, flexShrink: 0 }}>→</span>
          <input
            style={{ ...inputStyle }}
            type="text"
            value={route.agent}
            placeholder="builder"
            onChange={(e) => updateRoute(idx, { agent: e.target.value })}
          />
          <button style={styles.removeBtn} onClick={() => removeRoute(idx)} aria-label="Remove route">×</button>
        </div>
      ))}

      <button style={styles.addBtn} onClick={addRoute}>+ Add route</button>

      {unusedCommon.length > 0 && (
        <div style={{ marginTop: '16px' }}>
          <div style={{ fontSize: '11px', color: styles.stepSub?.color, marginBottom: '6px' }}>Quick-add common tags:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {unusedCommon.map((tag) => (
              <button
                key={tag}
                style={{
                  background: 'none',
                  border: `1px solid ${styles.addBtn?.borderColor ?? '#444'}`,
                  borderRadius: '4px',
                  color: styles.addBtn?.color,
                  cursor: 'pointer',
                  fontSize: '11px',
                  padding: '3px 8px',
                  fontFamily: 'monospace',
                }}
                onClick={() => onSetRoutes([...feedbackRoutes, { tag, agent: '' }])}
              >
                {tag}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
