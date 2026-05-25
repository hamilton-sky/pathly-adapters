import { useState, useEffect, useCallback, useRef } from 'react'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import { fsmPing, readFile, listDir } from '../../services/pathlyApi'
import { Tooltip } from '../ui/Tooltip'

type CheckStatus = 'pass' | 'warn' | 'fail' | 'loading'

interface CheckItem {
  label: string
  status: CheckStatus
  detail: string
}

function statusDot(status: CheckStatus, t: ReturnType<typeof useTheme>): { symbol: string; color: string } {
  switch (status) {
    case 'pass':    return { symbol: '●', color: t.green }
    case 'warn':    return { symbol: '●', color: t.yellow }
    case 'fail':    return { symbol: '●', color: t.red }
    case 'loading': return { symbol: '○', color: t.textMuted }
  }
}

async function runHealthChecks(projectPath: string, topic: string | null): Promise<CheckItem[]> {
  const items: CheckItem[] = []

  // 1. FSM server reachability
  try {
    const alive = await fsmPing()
    items.push({
      label: 'FSM server',
      status: alive ? 'pass' : 'fail',
      detail: alive ? 'port 8765 responding' : 'not reachable',
    })
  } catch {
    items.push({ label: 'FSM server', status: 'fail', detail: 'not reachable' })
  }

  if (!topic || !projectPath) {
    items.push({ label: 'Feature state', status: 'warn', detail: 'no topic selected' })
    return items
  }

  // 2. STATE.json presence
  const roots = [
    `${projectPath}/pathly/plans/${topic}`,
    `${projectPath}/pathly/debugs/${topic}`,
    `${projectPath}/pathly/explorations/${topic}`,
  ]

  let stateFound = false
  for (const root of roots) {
    try {
      const content = await readFile(`${root}/STATE.json`)
      if (content) {
        let current = '—'
        try { current = (JSON.parse(content) as { current?: string }).current ?? '—' } catch { /* ok */ }
        items.push({ label: 'STATE.json', status: 'pass', detail: `state: ${current}` })
        stateFound = true
        break
      }
    } catch { /* try next root */ }
  }
  if (!stateFound) {
    items.push({ label: 'STATE.json', status: 'warn', detail: 'not found in any root' })
  }

  // 3. Open feedback files
  try {
    const files = await listDir(`${projectPath}/pathly/plans/${topic}/feedback`)
    const open = files.filter((f) => f.endsWith('.md'))
    items.push({
      label: 'Feedback files',
      status: open.length > 0 ? 'warn' : 'pass',
      detail: open.length > 0
        ? `${open.length} open: ${open.map((f) => f.split('/').pop() ?? f).join(', ')}`
        : 'none open',
    })
  } catch {
    items.push({ label: 'Feedback files', status: 'pass', detail: 'none' })
  }

  // 4. Event log existence
  try {
    const content = await readFile(`${projectPath}/pathly/plans/${topic}/EVENTS.jsonl`)
    const lines = content ? content.trim().split('\n').filter(Boolean).length : 0
    items.push({
      label: 'Event log',
      status: lines > 0 ? 'pass' : 'warn',
      detail: lines > 0 ? `${lines} events` : 'empty',
    })
  } catch {
    items.push({ label: 'Event log', status: 'warn', detail: 'not found' })
  }

  return items
}

// Strip item labels match the 4 checks in order
const STRIP_LABELS = ['FSM', 'State', 'Feedback', 'Events']

export function HealthCheck(): JSX.Element {
  const { projectPath, activeTopic, activeMonitorTab, activeFlowSessions } = useStore()
  const t = useTheme()
  const containerRef = useRef<HTMLDivElement>(null)

  const [expanded, setExpanded] = useState(false)
  const [hovered, setHovered] = useState(false)
  const [checks, setChecks] = useState<CheckItem[]>([])
  const [running, setRunning] = useState(false)

  const effectiveTopic = (activeMonitorTab && activeFlowSessions[activeMonitorTab])
    ? activeMonitorTab
    : activeTopic

  const run = useCallback((): void => {
    if (!projectPath) return
    setRunning(true)
    setChecks([
      { label: 'FSM server',     status: 'loading', detail: '…' },
      { label: 'STATE.json',     status: 'loading', detail: '…' },
      { label: 'Feedback files', status: 'loading', detail: '…' },
      { label: 'Event log',      status: 'loading', detail: '…' },
    ])
    runHealthChecks(projectPath, effectiveTopic ?? null)
      .then((results) => { setChecks(results) })
      .catch(() => { /* keep loading state */ })
      .finally(() => { setRunning(false) })
  }, [projectPath, effectiveTopic])

  // Auto-run when project/topic changes (not gated on expanded)
  useEffect(() => {
    run()
  }, [effectiveTopic, projectPath]) // eslint-disable-line react-hooks/exhaustive-deps

  // 4 slot statuses for strip dots — pad with loading if checks not ready
  const slotStatuses: CheckStatus[] = STRIP_LABELS.map((_, i) =>
    checks[i]?.status ?? 'loading'
  )

  return (
    <div ref={containerRef} style={{ flexShrink: 0, position: 'relative' }}>
      {/* 24px strip — label LEFT (VSCode pattern): ▾ Health · ● FSM ● State ● Feedback ● Events */}
      <div
        role="button"
        aria-expanded={expanded}
        aria-label={expanded ? 'Collapse health details' : 'Expand health details'}
        tabIndex={0}
        onClick={() => setExpanded((v) => !v)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setExpanded((v) => !v) }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          height: '24px',
          display: 'flex',
          alignItems: 'center',
          gap: '0',
          padding: '0 12px',
          backgroundColor: hovered ? t.bgSurface0 : t.bgMantle,
          borderBottom: `1px solid ${t.bgSurface0}`,
          cursor: 'pointer',
          userSelect: 'none',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          transition: 'background-color 150ms ease',
        }}
      >
        {/* ▾ Health — section label + toggle cue, left-anchored */}
        <span style={{ display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0, marginRight: '10px' }}>
          <span
            aria-hidden="true"
            style={{
              display: 'inline-block',
              transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)',
              transition: 'transform 150ms ease',
              fontSize: '9px',
              color: expanded ? t.accent : t.textMuted,
              lineHeight: 1,
            }}
          >▾</span>
          <span style={{
            fontSize: '11px',
            fontWeight: 500,
            color: expanded ? t.accent : t.textSecondary,
            letterSpacing: '0.03em',
            transition: 'color 150ms ease',
          }}>Health</span>
        </span>

        {/* Thin divider */}
        <span style={{ width: '1px', height: '12px', backgroundColor: t.bgSurface1, flexShrink: 0, marginRight: '10px' }} />

        {/* Summary dots — tooltip shows live check detail */}
        {STRIP_LABELS.map((label, i) => {
          const d = statusDot(slotStatuses[i], t)
          const detail = checks[i]?.detail ?? '…'
          const statusLabel = checks[i]?.status ?? 'loading'
          return (
            <Tooltip key={label} label={`${label}: ${detail}`} placement="bottom" delay={200}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px', marginRight: '10px' }}>
                <span style={{ color: d.color, fontSize: '7px' }} aria-hidden="true">{d.symbol}</span>
                <span style={{
                  fontSize: '11px',
                  color: statusLabel === 'fail' ? t.red : statusLabel === 'warn' ? t.yellow : t.textMuted,
                }}>{label}</span>
              </span>
            </Tooltip>
          )
        })}

        {/* Far-right: running spinner only */}
        {running && (
          <span style={{ marginLeft: 'auto', color: t.textMuted, fontSize: '10px' }}>…</span>
        )}
      </div>

      {/* Inline popover */}
      {expanded && (
        <div
          style={{
            position: 'absolute',
            top: '24px',
            left: 0,
            right: 0,
            zIndex: 20,
            backgroundColor: t.bgSurface0,
            border: `1px solid ${t.bgSurface1}`,
            padding: '8px 12px',
          }}
        >
          {checks.map((item) => {
            const d = statusDot(item.status, t)
            return (
              <div
                key={item.label}
                style={{
                  display: 'flex',
                  alignItems: 'baseline',
                  gap: '8px',
                  padding: '2px 0',
                  fontSize: '12px',
                  fontFamily: 'system-ui, -apple-system, sans-serif',
                }}
              >
                <span style={{ color: d.color, fontSize: '8px', lineHeight: '18px' }} aria-hidden="true">
                  {d.symbol}
                </span>
                <span style={{ color: t.textMuted, minWidth: '110px', flexShrink: 0 }}>{item.label}</span>
                <span style={{ color: t.textSecondary, fontFamily: t.fontFamilyMono, fontSize: '11px' }}>{item.detail}</span>
              </div>
            )
          })}
          {checks.length === 0 && (
            <div style={{ color: t.textMuted, fontSize: '12px' }}>Running checks…</div>
          )}
        </div>
      )}
    </div>
  )
}
