import { useRef, useEffect } from 'react'
import styles from './AgentsTab.module.css'
import { computeCost } from '../costUtils'
import type { PricingTable } from '../costUtils'

interface AgentsTabProps {
  events: DbEvent[]
  pricingTable: PricingTable | null
}

type AgentRow = {
  agent: string
  conversation: number
  model: string
  totalTokens: number
  costUsd: number | null
  costSource: string | null
  wallSeconds: number
  result: string
  traceId: string
}

function parseAgentDone(payload: Record<string, unknown>, pricingTable: PricingTable | null): AgentRow {
  const stored = Number(payload.cost_usd ?? 0)
  let costUsd: number | null = null
  let costSource: string | null = null
  if (stored > 0) {
    costUsd = stored
    costSource = 'provider_reported'
  } else {
    const result = computeCost(
      String(payload.model ?? ''),
      Number(payload.tokens_in ?? 0),
      Number(payload.tokens_out ?? 0),
      pricingTable,
    )
    costUsd = result.cost
    costSource = result.source
  }
  return {
    agent: String(payload.agent ?? payload.agent_role ?? 'unknown'),
    conversation: Number(payload.conversation ?? payload.conv ?? 0),
    model: String(payload.model ?? '—'),
    totalTokens: Number(
      payload.total_tokens ??
      (Number(payload.tokens_in ?? 0) + Number(payload.tokens_out ?? 0))
    ),
    costUsd,
    costSource,
    wallSeconds: Number(payload.wall_seconds ?? 0),
    result: String(payload.result ?? '—'),
    traceId: String(payload.trace_id ?? '—'),
  }
}

function roleColor(role: string): string {
  const r = role.toLowerCase()
  if (r === 'builder') return 'var(--state-building)'
  if (r.includes('review')) return 'var(--state-reviewing)'
  if (r.includes('test')) return 'var(--state-testing)'
  if (r.includes('plan')) return 'var(--state-planning)'
  return 'var(--accent)'
}

function resultKind(result: string): 'pass' | 'fail' | 'done' {
  const r = result.toLowerCase()
  if (r.startsWith('pass')) return 'pass'
  if (r.includes('fail') || r.includes('error')) return 'fail'
  return 'done'
}

function fmtWall(s: number): string {
  if (s < 60) return `${s.toFixed(1)}s`
  const m = Math.floor(s / 60)
  return `${m}m ${Math.round(s % 60)}s`
}

export function AgentsTab({ events, pricingTable }: AgentsTabProps): JSX.Element {
  const rows = events
    .filter((e) => e.event_type === 'AGENT_DONE')
    .map((e) => parseAgentDone(e.payload, pricingTable))

  const knownCosts = rows.filter((r) => r.costUsd !== null)
  const totalCost = knownCosts.reduce((s, r) => s + (r.costUsd ?? 0), 0)
  const maxCost = Math.max(...rows.map((r) => r.costUsd ?? 0), 0.001)
  const barRefs = useRef<(HTMLDivElement | null)[]>([])

  useEffect(() => {
    rows.forEach((row, i) => {
      const el = barRefs.current[i]
      if (!el) return
      el.style.setProperty('--bar-w', `${((row.costUsd ?? 0) / maxCost) * 100}%`)
      el.style.setProperty('--bar-color', roleColor(row.agent))
    })
  }, [rows, maxCost])

  if (rows.length === 0) {
    return <p className={styles.empty}>No AGENT_DONE events yet.</p>
  }

  return (
    <div className={styles.container}>
      <section className={styles.section}>
        <header className={styles.sectionHead}>
          <span className={styles.sectionTitle}>Cost per invocation</span>
          <span className={styles.sectionMeta}>
            {rows.length} agents · {knownCosts.length > 0 ? `$${totalCost.toFixed(2)} total` : '—'}
          </span>
        </header>
        <div className={styles.bars}>
          {rows.map((row, i) => (
            <div key={i} className={styles.barRow}>
              <span className={styles.barLabel}>
                <RoleTag role={row.agent} />
                <span className={styles.convLabel}>(conv {row.conversation})</span>
              </span>
              <div className={styles.barTrack}>
                <div ref={(el) => { barRefs.current[i] = el }} className={styles.bar} />
              </div>
              {row.costUsd !== null
                ? <span className={styles.barCost}>${row.costUsd.toFixed(2)}</span>
                : <span className={styles.barCostNull}>—</span>
              }
            </div>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <header className={styles.sectionHead}>
          <span className={styles.sectionTitle}>Agent invocations</span>
          <span className={styles.sectionMeta}>AGENT_DONE event detail</span>
        </header>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.th}>#</th>
                <th className={styles.th}>AGENT</th>
                <th className={styles.thC}>CONV</th>
                <th className={styles.th}>MODEL</th>
                <th className={styles.thR}>TOKENS</th>
                <th className={styles.thR}>COST</th>
                <th className={styles.thR}>WALL</th>
                <th className={styles.th}>RESULT</th>
                <th className={styles.th}>TRACE_ID</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className={styles.tr}>
                  <td className={styles.tdNum}>{i + 1}</td>
                  <td className={styles.td}><RoleTag role={row.agent} /></td>
                  <td className={styles.tdC}>{row.conversation}</td>
                  <td className={styles.tdMono}>{row.model}</td>
                  <td className={styles.tdR}>{row.totalTokens.toLocaleString()}</td>
                  <td className={row.costUsd !== null ? styles.tdCost : styles.tdCostNull}>
                    {row.costUsd !== null ? `$${row.costUsd.toFixed(2)}` : '—'}
                    {row.costSource !== null && (
                      <span className={styles.sourceBadge} data-source={row.costSource}>
                        {row.costSource === 'provider_reported' ? 'reported' : row.costSource}
                      </span>
                    )}
                  </td>
                  <td className={styles.tdR}>{fmtWall(row.wallSeconds)}</td>
                  <td className={styles.td}><ResultPill result={row.result} /></td>
                  <td className={styles.tdTrace}>{row.traceId.slice(0, 8)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function RoleTag({ role }: { role: string }): JSX.Element {
  const ref = (el: HTMLSpanElement | null): void => {
    if (el) el.style.setProperty('--role-color', roleColor(role))
  }
  return <span className={styles.roleTag} ref={ref}>{role}</span>
}

function ResultPill({ result }: { result: string }): JSX.Element {
  return (
    <span className={styles.resultPill} data-kind={resultKind(result)}>
      {result}
    </span>
  )
}
