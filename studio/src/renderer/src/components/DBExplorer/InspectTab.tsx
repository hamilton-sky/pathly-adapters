import { useState, useEffect, useMemo } from 'react'
import styles from './InspectTab.module.css'
import { computeCost } from './costUtils'

interface InspectTabProps {
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

interface TypeStat {
  type: string
  count: number
  firstTs: string
  lastTs: string
  totalCost?: number
}

export function InspectTab({ events }: InspectTabProps): JSX.Element {
  const allTypes = useMemo(
    () => Array.from(new Set(events.map((e) => e.event_type))).sort(),
    [events],
  )

  const [disabled, setDisabled] = useState<Set<string>>(new Set())

  useEffect(() => { setDisabled(new Set()) }, [events])

  const stats = useMemo((): TypeStat[] => {
    const map = new Map<string, DbEvent[]>()
    for (const e of events) {
      const list = map.get(e.event_type) ?? []
      list.push(e)
      map.set(e.event_type, list)
    }
    return Array.from(map.entries())
      .map(([type, evts]) => {
        const sorted = [...evts].sort((a, b) => a.seq - b.seq)
        return {
          type,
          count: evts.length,
          firstTs: sorted[0]?.ts.slice(11, 19) ?? '—',
          lastTs: sorted[sorted.length - 1]?.ts.slice(11, 19) ?? '—',
          totalCost: type === 'AGENT_DONE'
            ? evts.reduce((s, e) => {
                const p = e.payload as Record<string, unknown>
                const stored = Number(p.cost_usd ?? 0)
                return s + (stored > 0
                  ? stored
                  : computeCost(String(p.model ?? ''), Number(p.tokens_in ?? 0), Number(p.tokens_out ?? 0)))
              }, 0)
            : undefined,
        }
      })
      .sort((a, b) => b.count - a.count)
  }, [events])

  const maxCount = Math.max(...stats.map((s) => s.count), 1)
  const activeStats = stats.filter((s) => !disabled.has(s.type))

  function toggle(type: string): void {
    setDisabled((prev) => {
      const next = new Set(prev)
      next.has(type) ? next.delete(type) : next.add(type)
      return next
    })
  }

  if (events.length === 0) {
    return <p className={styles.empty}>No events to inspect.</p>
  }

  return (
    <div className={styles.container}>
      <div className={styles.chipsRow}>
        {allTypes.map((type) => (
          <button
            key={type}
            type="button"
            className={styles.chip}
            data-category={typeCategory(type)}
            {...(disabled.has(type) ? {} : { 'data-active': '' })}
            onClick={() => toggle(type)}
            aria-pressed={!disabled.has(type)}
          >
            {type}
          </button>
        ))}
        {disabled.size > 0 && (
          <button
            type="button"
            className={styles.chipReset}
            onClick={() => setDisabled(new Set())}
          >
            show all
          </button>
        )}
      </div>

      <div className={styles.statsList}>
        {activeStats.length === 0
          ? <p className={styles.empty}>No types selected — click a chip above to enable.</p>
          : activeStats.map((stat) => (
              <div key={stat.type} className={styles.statRow}>
                <span className={styles.statLabel} data-category={typeCategory(stat.type)}>
                  {stat.type}
                </span>
                <div className={styles.barTrack}>
                  <div
                    className={styles.bar}
                    data-category={typeCategory(stat.type)}
                    ref={(el) => {
                      if (el) el.style.setProperty('--bar-w', `${(stat.count / maxCount) * 100}%`)
                    }}
                  />
                </div>
                <span className={styles.statCount}>{stat.count}</span>
                <span className={styles.statWindow}>
                  {stat.firstTs === stat.lastTs
                    ? stat.firstTs
                    : `${stat.firstTs} → ${stat.lastTs}`}
                  {stat.totalCost !== undefined && (
                    <b className={styles.statCost}> · ${stat.totalCost.toFixed(2)}</b>
                  )}
                </span>
              </div>
            ))}
      </div>
    </div>
  )
}
