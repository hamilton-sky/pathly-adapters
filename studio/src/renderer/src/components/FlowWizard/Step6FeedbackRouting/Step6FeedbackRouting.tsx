import type { FeedbackRoute } from '../types'
import styles from './Step6FeedbackRouting.module.css'

interface Step6FeedbackRoutingProps {
  feedbackRoutes: FeedbackRoute[]
  onSetRoutes: (routes: FeedbackRoute[]) => void
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

export function Step6FeedbackRouting({ feedbackRoutes, onSetRoutes }: Step6FeedbackRoutingProps): JSX.Element {
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

  return (
    <div className={styles.root}>
      <div className={styles.desc}>
        When an agent writes a feedback file (e.g. <code>REVIEW_FAILURES.md</code>), the FSM routes it to the mapped agent.
      </div>

      {feedbackRoutes.map((route, idx) => (
        <div key={idx} className={styles.routeRow}>
          <input
            className={styles.input}
            type="text"
            list={`tag-suggestions-${idx}`}
            value={route.tag}
            placeholder="REVIEW_FAILURES"
            onChange={(e) => updateRoute(idx, { tag: e.target.value.toUpperCase() })}
          />
          <datalist id={`tag-suggestions-${idx}`}>
            {COMMON_TAGS.map((t) => <option key={t} value={t} />)}
          </datalist>
          <span className={styles.arrow}>→</span>
          <input
            className={styles.input}
            type="text"
            value={route.agent}
            placeholder="builder"
            onChange={(e) => updateRoute(idx, { agent: e.target.value })}
          />
          <button type="button" className={styles.removeBtn} onClick={() => removeRoute(idx)} aria-label="Remove route">×</button>
        </div>
      ))}

      <button type="button" className={styles.addBtn} onClick={addRoute}>+ Add route</button>

      {unusedCommon.length > 0 && (
        <div className={styles.quickAdd}>
          <div className={styles.quickAddLabel}>Quick-add common tags:</div>
          <div className={styles.tagList}>
            {unusedCommon.map((tag) => (
              <button
                key={tag}
                type="button"
                className={styles.tagBtn}
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
