import { useState, useEffect, useCallback } from 'react'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import { mcpPing, readFile, listDir } from '../../services/pathlyApi'
import type { Theme } from '../../theme'

type CheckStatus = 'pass' | 'warn' | 'fail' | 'loading'

interface CheckItem {
  label: string
  status: CheckStatus
  detail: string
}

function makeStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    section: {
      flexShrink: 0,
      borderTop: `1px solid ${t.bgSurface0}`,
    },
    sectionHeader: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '5px 12px',
      backgroundColor: t.bgSurface0,
      cursor: 'pointer',
      userSelect: 'none',
      fontSize: '12px',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      color: t.textSecondary,
    },
    headerLeft: {
      display: 'flex',
      alignItems: 'center',
      gap: '6px',
    },
    body: {
      backgroundColor: t.bgBase,
      padding: '6px 12px 8px',
    },
    row: {
      display: 'flex',
      alignItems: 'baseline',
      gap: '8px',
      padding: '2px 0',
      fontSize: '12px',
      fontFamily: 'system-ui, -apple-system, sans-serif',
    },
    label: {
      color: t.textMuted,
      minWidth: '110px',
      flexShrink: 0,
    },
    detail: {
      color: t.textSecondary,
      fontFamily: t.fontFamilyMono,
      fontSize: '11px',
    },
    refreshBtn: {
      fontSize: '11px',
      color: t.textMuted,
      background: 'none',
      border: 'none',
      cursor: 'pointer',
      padding: '0',
      fontFamily: 'system-ui, -apple-system, sans-serif',
    },
  }
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
    const alive = await mcpPing()
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

export function HealthCheck(): JSX.Element {
  const { projectPath, activeTopic, activeMonitorTab, activeFlowSessions } = useStore()
  const t = useTheme()
  const styles = makeStyles(t)

  const [expanded, setExpanded] = useState(false)
  const [checks, setChecks] = useState<CheckItem[]>([])
  const [running, setRunning] = useState(false)

  const effectiveTopic = (activeMonitorTab && activeFlowSessions[activeMonitorTab])
    ? activeMonitorTab
    : activeTopic

  const run = useCallback((): void => {
    if (!projectPath) return
    setRunning(true)
    // Set all to loading
    setChecks([
      { label: 'FSM server',    status: 'loading', detail: '…' },
      { label: 'STATE.json',    status: 'loading', detail: '…' },
      { label: 'Feedback files', status: 'loading', detail: '…' },
      { label: 'Event log',     status: 'loading', detail: '…' },
    ])
    runHealthChecks(projectPath, effectiveTopic ?? null)
      .then((results) => { setChecks(results) })
      .catch(() => { /* keep loading state */ })
      .finally(() => { setRunning(false) })
  }, [projectPath, effectiveTopic])

  // Auto-run when topic/project changes and panel is expanded
  useEffect(() => {
    if (expanded) run()
  }, [expanded, effectiveTopic, projectPath]) // eslint-disable-line react-hooks/exhaustive-deps

  // Derive summary badge from completed checks
  const overallStatus: CheckStatus = (() => {
    if (checks.length === 0 || checks.some((c) => c.status === 'loading')) return 'loading'
    if (checks.some((c) => c.status === 'fail'))  return 'fail'
    if (checks.some((c) => c.status === 'warn'))  return 'warn'
    return 'pass'
  })()

  const dot = statusDot(overallStatus, t)

  return (
    <div style={styles.section}>
      <div
        style={styles.sectionHeader}
        onClick={() => {
          const next = !expanded
          setExpanded(next)
          if (next && checks.length === 0) run()
        }}
        role="button"
        aria-expanded={expanded}
        aria-label="Health check panel"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setExpanded((v) => !v) }}
      >
        <span style={styles.headerLeft}>
          <span style={{ color: dot.color, fontSize: '8px' }} aria-hidden="true">{dot.symbol}</span>
          <span>Health</span>
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {expanded && (
            <button
              style={styles.refreshBtn}
              onClick={(e) => { e.stopPropagation(); run() }}
              disabled={running}
              aria-label="Refresh health checks"
            >
              {running ? '…' : '↺'}
            </button>
          )}
          <span aria-hidden="true" style={{ fontSize: '10px', color: t.textMuted }}>{expanded ? '▲' : '▼'}</span>
        </span>
      </div>

      {expanded && (
        <div style={styles.body}>
          {checks.map((item) => {
            const d = statusDot(item.status, t)
            return (
              <div key={item.label} style={styles.row}>
                <span style={{ color: d.color, fontSize: '8px', lineHeight: '18px' }} aria-hidden="true">
                  {d.symbol}
                </span>
                <span style={styles.label}>{item.label}</span>
                <span style={styles.detail}>{item.detail}</span>
              </div>
            )
          })}
          {checks.length === 0 && (
            <div style={{ ...styles.row, color: t.textMuted }}>Click ↺ to run checks</div>
          )}
        </div>
      )}
    </div>
  )
}
