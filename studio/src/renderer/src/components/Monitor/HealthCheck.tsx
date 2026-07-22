import { useState, useEffect, useCallback, useRef } from 'react'
import { useStore } from '../../store'
import { fsmPing, listDir } from '../../services/pathlyApi'
import { fetchDbFeatureMap } from '../../store/commsApi'
import { Tooltip } from '../ui/Tooltip/Tooltip'
import styles from './Monitor.module.css'

type CheckStatus = 'pass' | 'warn' | 'fail' | 'loading'

interface CheckItem {
  label: string
  status: CheckStatus
  detail: string
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

  // 2. Feature state — DB-first /db/features row (state-one-authority: no STATE.json
  // mirror probe; the row covers features/debugs/explorations + the server-side
  // filesystem fallback for never-run features).
  let row: DbFeature | undefined
  try {
    row = (await fetchDbFeatureMap(projectPath, { fresh: true })).get(topic)
  } catch { /* row stays undefined */ }
  if (row) {
    const current = row.state !== 'UNKNOWN' ? row.state : '—'
    items.push({ label: 'Feature state', status: 'pass', detail: `state: ${current}` })
  } else {
    items.push({ label: 'Feature state', status: 'warn', detail: 'no feature row found' })
  }

  // 3. Open feedback files
  try {
    const files = await listDir(`${projectPath}/pathly/features/${topic}/feedback`)
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

  // 4. Event log — the same DB row's event count (state-one-authority: no
  // EVENTS.jsonl mirror read).
  const eventCount = row?.events ?? 0
  items.push({
    label: 'Event log',
    status: eventCount > 0 ? 'pass' : 'warn',
    detail: eventCount > 0 ? `${eventCount} events` : row ? 'empty' : 'not found',
  })

  return items
}

const STRIP_LABELS = ['FSM', 'State', 'Feedback', 'Events']

function dotSymbol(status: CheckStatus): string {
  return status === 'loading' ? '○' : '●'
}

function dotClass(status: CheckStatus): string {
  const map: Record<CheckStatus, string> = {
    pass: styles.healthDotPass,
    warn: styles.healthDotWarn,
    fail: styles.healthDotFail,
    loading: styles.healthDotLoading,
  }
  return map[status]
}

function slotLabelClass(status: CheckStatus): string {
  const map: Record<CheckStatus, string> = {
    pass: styles.healthSlotLabelMuted,
    warn: styles.healthSlotLabelWarn,
    fail: styles.healthSlotLabelFail,
    loading: styles.healthSlotLabelMuted,
  }
  return map[status]
}

export function HealthCheck(): JSX.Element {
  const { projectPath, activeTopic, activeMonitorTab, activeFlowSessions } = useStore()
  const containerRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)

  const [expanded, setExpanded] = useState(false)
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
      { label: 'Feature state',  status: 'loading', detail: '…' },
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

  // Set aria-expanded imperatively to avoid JSX expression lint false-positive
  useEffect(() => {
    buttonRef.current?.setAttribute('aria-expanded', String(expanded))
  }, [expanded])

  const slotStatuses: CheckStatus[] = STRIP_LABELS.map((_, i) =>
    checks[i]?.status ?? 'loading'
  )

  return (
    <div ref={containerRef} className={styles.healthRoot}>
      <button
        ref={buttonRef}
        type="button"
        aria-label="Toggle health details"
        onClick={() => setExpanded((v) => !v)}
        className={styles.healthStrip}
      >
        <span className={styles.healthLabel}>
          <span
            aria-hidden="true"
            className={`${styles.healthChevron} ${expanded ? styles.healthChevronExpanded : styles.healthChevronCollapsed}`}
          >▾</span>
          <span className={`${styles.healthTitle} ${expanded ? styles.healthTitleExpanded : ''}`}>
            Health
          </span>
        </span>

        <span className={styles.healthDivider} />

        {STRIP_LABELS.map((label, i) => {
          const status = slotStatuses[i]
          const detail = checks[i]?.detail ?? '…'
          return (
            <Tooltip key={label} label={`${label}: ${detail}`} placement="bottom" delay={200}>
              <span className={styles.healthSlot}>
                <span className={`${styles.healthDot} ${dotClass(status)}`} aria-hidden="true">
                  {dotSymbol(status)}
                </span>
                <span className={`${styles.healthSlotLabel} ${slotLabelClass(status)}`}>
                  {label}
                </span>
              </span>
            </Tooltip>
          )
        })}

        {running && <span className={styles.healthSpinner}>…</span>}
      </button>

      {expanded && (
        <div className={styles.healthPopover}>
          {checks.map((item) => (
            <div key={item.label} className={styles.healthPopoverRow}>
              <span className={`${styles.healthPopoverDot} ${dotClass(item.status)}`} aria-hidden="true">
                {dotSymbol(item.status)}
              </span>
              <span className={styles.healthPopoverLabel}>{item.label}</span>
              <span className={styles.healthPopoverDetail}>{item.detail}</span>
            </div>
          ))}
          {checks.length === 0 && (
            <div className={styles.healthEmpty}>Running checks…</div>
          )}
        </div>
      )}
    </div>
  )
}
