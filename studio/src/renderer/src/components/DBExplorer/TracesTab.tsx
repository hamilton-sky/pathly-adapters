import { useRef, useEffect } from 'react'
import styles from './TracesTab.module.css'

interface TracesTabProps {
  spans: DbOtelSpan[]
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function attr<T>(span: DbOtelSpan, key: string, fallback: T): T {
  const v = span.attributes[key]
  return v !== undefined && v !== null ? (v as T) : fallback
}

function parseDurationMs(span: DbOtelSpan): number {
  const s = span.start_time
  const e = span.end_time
  if (!s || !e) return 0
  return Math.max(0, new Date(e).getTime() - new Date(s).getTime())
}

function fmtDuration(ms: number): string {
  if (ms <= 0) return '—'
  if (ms < 1000) return `${ms}ms`
  const s = ms / 1000
  if (s < 60) return `${s.toFixed(1)}s`
  const m = Math.floor(s / 60)
  return `${m}m ${Math.round(s % 60)}s`
}

function fmtTime(iso: string | null): string {
  if (!iso) return '—'
  return iso.slice(11, 19)
}

function adapterFromModel(model: string): string {
  const m = model.toLowerCase()
  if (m.startsWith('claude-')) return 'claude'
  if (m.startsWith('gpt-') || m.startsWith('o1-') || m.startsWith('o3-') || m.startsWith('o4-')) return 'codex'
  if (m.startsWith('gemini-')) return 'google'
  return 'unknown'
}

function statusKind(result: string): 'ok' | 'error' | 'pending' {
  const r = result.toLowerCase()
  if (r === 'done' || r === 'pass') return 'ok'
  if (r.includes('fail') || r.includes('error')) return 'error'
  return 'pending'
}

function roleColor(role: string): string {
  const r = role.toLowerCase()
  if (r === 'builder') return 'var(--state-building)'
  if (r.includes('review')) return 'var(--state-reviewing)'
  if (r.includes('test')) return 'var(--state-testing)'
  if (r.includes('plan') || r.includes('architect')) return 'var(--state-planning)'
  return 'var(--accent)'
}

// ── Summary strip ─────────────────────────────────────────────────────────────

function SummaryStrip({ spans }: TracesTabProps): JSX.Element {
  const totalCost = spans.reduce((s, sp) => s + Number(attr(sp, 'pathly.cost_usd', 0)), 0)
  const adapters: Record<string, number> = {}
  for (const sp of spans) {
    const model = String(attr(sp, 'gen_ai.request.model', ''))
    const a = adapterFromModel(model)
    adapters[a] = (adapters[a] ?? 0) + 1
  }

  return (
    <div className={styles.strip}>
      <span className={styles.stripItem}>
        <b>{spans.length}</b> spans
      </span>
      <span className={styles.stripSep}>·</span>
      <span className={styles.stripItem}>
        <b className={styles.green}>${totalCost.toFixed(4)}</b> total
      </span>
      {Object.entries(adapters).map(([adapter, count]) => (
        <span key={adapter} className={styles.stripItem}>
          <span className={styles.stripSep}>·</span>
          {adapter}: <b>{count}</b>
        </span>
      ))}
    </div>
  )
}

// ── Span row ──────────────────────────────────────────────────────────────────

interface SpanRowProps {
  span: DbOtelSpan
  index: number
  maxDuration: number
}

function SpanRow({ span, index, maxDuration }: SpanRowProps): JSX.Element {
  const barRef = useRef<HTMLDivElement>(null)
  const agent  = String(attr(span, 'gen_ai.agent.name', '—'))
  const model  = String(attr(span, 'gen_ai.request.model', '—'))
  const tokIn  = Number(attr(span, 'gen_ai.usage.input_tokens', 0))
  const tokOut = Number(attr(span, 'gen_ai.usage.output_tokens', 0))
  const cost   = Number(attr(span, 'pathly.cost_usd', 0))
  const result = String(attr(span, 'pathly.result', ''))
  const dur    = parseDurationMs(span)
  const pct    = maxDuration > 0 ? (dur / maxDuration) * 100 : 0

  useEffect(() => {
    const el = barRef.current
    if (!el) return
    el.style.setProperty('--span-w', `${pct}%`)
    el.style.setProperty('--span-color', roleColor(agent))
  }, [pct, agent])

  return (
    <tr className={styles.tr}>
      <td className={styles.tdNum}>{index + 1}</td>
      <td className={styles.td}>
        <span className={styles.spanName}>{span.name ?? '—'}</span>
      </td>
      <td className={styles.td}>
        <span
          className={styles.roleTag}
          ref={(el) => { if (el) el.style.setProperty('--role-color', roleColor(agent)) }}
        >
          {agent}
        </span>
      </td>
      <td className={styles.tdMono}>{model}</td>
      <td className={styles.tdR}>{tokIn ? tokIn.toLocaleString() : '—'}</td>
      <td className={styles.tdR}>{tokOut ? tokOut.toLocaleString() : '—'}</td>
      <td className={styles.tdCost}>{cost > 0 ? `$${cost.toFixed(4)}` : '—'}</td>
      <td className={styles.tdDur}>
        <div className={styles.durTrack}>
          <div ref={barRef} className={styles.durBar} />
        </div>
        <span className={styles.durLabel}>{fmtDuration(dur)}</span>
      </td>
      <td className={styles.td}>{fmtTime(span.start_time)}</td>
      <td className={styles.td}>
        <span className={styles.statusPill} data-kind={statusKind(result)}>
          {result || '—'}
        </span>
      </td>
    </tr>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function TracesTab({ spans }: TracesTabProps): JSX.Element {
  if (spans.length === 0) {
    return <p className={styles.empty}>No OTel spans yet. Agents write spans via /record_activity.</p>
  }

  const maxDuration = Math.max(...spans.map(parseDurationMs), 1)

  return (
    <div className={styles.container}>
      <SummaryStrip spans={spans} />
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.th}>#</th>
              <th className={styles.th}>SPAN</th>
              <th className={styles.th}>AGENT</th>
              <th className={styles.th}>MODEL</th>
              <th className={styles.thR}>TOK IN</th>
              <th className={styles.thR}>TOK OUT</th>
              <th className={styles.thR}>COST</th>
              <th className={styles.th}>DURATION</th>
              <th className={styles.th}>TIME</th>
              <th className={styles.th}>STATUS</th>
            </tr>
          </thead>
          <tbody>
            {spans.map((sp, i) => (
              <SpanRow key={sp.id} span={sp} index={i} maxDuration={maxDuration} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
