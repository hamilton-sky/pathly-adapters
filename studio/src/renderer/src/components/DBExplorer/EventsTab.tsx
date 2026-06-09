import { useState, useMemo } from 'react'
import styles from './EventsTab.module.css'

interface EventsTabProps {
  events: DbEvent[]
}

function typeCategory(type: string): string {
  if (['STATE_TRANSITION', 'STAGE_ENTER'].includes(type)) return 'transition'
  if (['AGENT_DONE', 'PIPELINE_DONE'].includes(type)) return 'done'
  if (type === 'PHASE_DONE') return 'phase-done'
  if (type === 'PHASE_START') return 'phase-start'
  if (['GATE_FAILED', 'STAGE_REROUTE'].includes(type)) return 'warning'
  if (['HUMAN_RESPONSE', 'HUMAN_QUESTIONS'].includes(type)) return 'human'
  return 'default'
}

function dotColorVar(type: string): string {
  if (['STATE_TRANSITION', 'STAGE_ENTER'].includes(type)) return 'var(--state-done)'
  if (['AGENT_DONE', 'PIPELINE_DONE'].includes(type)) return 'var(--accent)'
  if (['GATE_FAILED', 'STAGE_REROUTE'].includes(type)) return 'var(--orange)'
  if (['HUMAN_RESPONSE', 'HUMAN_QUESTIONS'].includes(type)) return 'var(--state-reviewing)'
  return 'var(--text-disabled)'
}

function summarize(payload: Record<string, unknown>): string {
  if (typeof payload.summary === 'string' && payload.summary) return payload.summary
  return JSON.stringify(payload)
}

export function EventsTab({ events }: EventsTabProps): JSX.Element {
  const [filter, setFilter] = useState('')
  const [expanded, setExpanded] = useState<number | null>(null)

  const sorted = useMemo(() => [...events].sort((a, b) => b.seq - a.seq), [events])

  const filtered = useMemo(() => {
    if (!filter.trim()) return sorted
    const q = filter.toLowerCase()
    return sorted.filter(
      (e) =>
        e.event_type.toLowerCase().includes(q) ||
        summarize(e.payload).toLowerCase().includes(q),
    )
  }, [sorted, filter])

  function toggleExpand(seq: number): void {
    setExpanded((prev) => (prev === seq ? null : seq))
  }

  return (
    <div className={styles.container}>
      <div className={styles.filterBar}>
        <input
          type="text"
          className={styles.filterInput}
          placeholder="Filter by type or payload…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          aria-label="Filter events"
          spellCheck={false}
        />
        <span className={styles.count}>
          {filtered.length} / {events.length} events
        </span>
      </div>

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.thSeq}>SEQ</th>
              <th className={styles.thType}>TYPE</th>
              <th className={styles.thTs}>TS</th>
              <th className={styles.thSummary}>SUMMARY</th>
            </tr>
          </thead>
          <tbody>
            {filtered.flatMap((ev) => [
              <tr
                key={ev.seq}
                className={styles.tr}
                {...(expanded === ev.seq ? { 'data-expanded': '' } : {})}
                onClick={() => toggleExpand(ev.seq)}
              >
                <td className={styles.tdSeq}>{ev.seq}</td>
                <td className={styles.tdType}>
                  <TypeBadge type={ev.event_type} />
                </td>
                <td className={styles.tdTs}>{ev.ts.slice(11, 19)}</td>
                <td className={styles.tdSummary}>{summarize(ev.payload)}</td>
              </tr>,
              ...(expanded === ev.seq
                ? [
                    <tr key={`${ev.seq}-exp`} className={styles.expandedRow}>
                      <td colSpan={4} className={styles.expandedCell}>
                        <pre className={styles.json}>
                          {JSON.stringify(ev.payload, null, 2)}
                        </pre>
                      </td>
                    </tr>,
                  ]
                : []),
            ])}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function TypeBadge({ type }: { type: string }): JSX.Element {
  const dotRef = (el: HTMLSpanElement | null): void => {
    if (el) el.style.setProperty('--dot-color', dotColorVar(type))
  }
  return (
    <span className={styles.typePill} data-category={typeCategory(type)}>
      <span className={styles.dot} ref={dotRef} />
      {type}
    </span>
  )
}
