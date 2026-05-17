import { useEffect, useState } from 'react'
import { useStore } from '../store'

interface ConvRow {
  num: number
  title: string
  status: string
}

interface EventEntry {
  type: string
  agent?: string
  conversation?: number
  result?: string
  to?: string
  cost_usd?: number
  wall_seconds?: number
  timestamp?: string
  ts?: string
}

interface CardState {
  expanded: boolean
}

function parseProgressMd(md: string): ConvRow[] {
  const rows: ConvRow[] = []
  for (const line of md.split('\n')) {
    const parts = line.split('|').map((p) => p.trim())
    if (parts.length < 5) continue
    const num = parseInt(parts[1], 10)
    if (isNaN(num)) continue
    rows.push({ num, title: parts[2], status: parts[4].toUpperCase() })
  }
  return rows
}

function fsmStateColor(state: string): string {
  if (state === 'DONE') return '#a6e3a1'
  if (state === 'BUILDING' || state === 'REVIEWING') return '#89b4fa'
  if (state === 'BLOCKED') return '#f38ba8'
  return '#6c7086'
}

function statusBorderColor(status: string): string {
  if (status === 'DONE') return '#a6e3a1'
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING') return '#89b4fa'
  if (status === 'BLOCKED') return '#f38ba8'
  return '#6c7086'
}

function statusBgColor(status: string): string {
  if (status === 'DONE') return 'rgba(166,227,161,0.05)'
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING')
    return 'rgba(137,180,250,0.05)'
  if (status === 'BLOCKED') return 'rgba(243,139,168,0.05)'
  return 'rgba(108,112,134,0.05)'
}

export function PlanBoard(): JSX.Element {
  const { projectPath, activeTopic } = useStore()

  const [fsmState, setFsmState] = useState<string>('')
  const [convs, setConvs] = useState<ConvRow[]>([])
  const [events, setEvents] = useState<EventEntry[]>([])
  const [cardStates, setCardStates] = useState<Record<number, CardState>>({})
  const [noProgress, setNoProgress] = useState(false)

  useEffect(() => {
    if (!projectPath || !activeTopic) {
      setFsmState('')
      setConvs([])
      setEvents([])
      setNoProgress(false)
      return
    }

    const base = `${projectPath}/pathly/plans/${activeTopic}`

    async function loadAll(): Promise<void> {
      // Load STATE.json
      try {
        const raw = await window.pathly.fs.read(`${base}/STATE.json`)
        const parsed = JSON.parse(raw) as { current?: string }
        setFsmState(parsed.current ?? '')
      } catch {
        setFsmState('')
      }

      // Load PROGRESS.md
      try {
        const md = await window.pathly.fs.read(`${base}/PROGRESS.md`)
        const rows = parseProgressMd(md)
        setConvs(rows)
        setNoProgress(rows.length === 0)
      } catch {
        setConvs([])
        setNoProgress(true)
      }

      // Load EVENTS.jsonl
      try {
        const raw = await window.pathly.fs.read(`${base}/EVENTS.jsonl`)
        const parsed: EventEntry[] = []
        for (const line of raw.split('\n')) {
          const trimmed = line.trim()
          if (!trimmed) continue
          try {
            parsed.push(JSON.parse(trimmed) as EventEntry)
          } catch {
            // skip malformed lines
          }
        }
        setEvents(parsed)
      } catch {
        setEvents([])
      }
    }

    loadAll()
  }, [projectPath, activeTopic])

  function toggleCard(num: number): void {
    setCardStates((prev) => ({
      ...prev,
      [num]: { expanded: !prev[num]?.expanded }
    }))
  }

  if (!activeTopic) {
    return (
      <div style={styles.container}>
        <div style={styles.placeholder}>Select a topic to view its plan</div>
      </div>
    )
  }

  if (noProgress && convs.length === 0) {
    return (
      <div style={styles.container}>
        <div style={styles.header}>
          <span style={styles.planName}>{activeTopic}</span>
          {fsmState && (
            <span style={{ ...styles.fsmBadge, backgroundColor: fsmStateColor(fsmState) }}>
              {fsmState}
            </span>
          )}
        </div>
        <div style={styles.placeholder}>No PROGRESS.md found for this plan</div>
      </div>
    )
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.planName}>{activeTopic}</span>
        {fsmState && (
          <span style={{ ...styles.fsmBadge, backgroundColor: fsmStateColor(fsmState) }}>
            {fsmState}
          </span>
        )}
      </div>

      <div style={styles.cardList}>
        {convs.map((conv) => {
          const isExpanded = cardStates[conv.num]?.expanded ?? false
          const convEvents = events.filter((e) => e.conversation === conv.num)
          const borderColor = statusBorderColor(conv.status)
          const bgColor = statusBgColor(conv.status)

          return (
            <div
              key={conv.num}
              style={{
                ...styles.card,
                borderLeft: `3px solid ${borderColor}`,
                backgroundColor: bgColor
              }}
            >
              <button style={styles.cardHeader} onClick={() => toggleCard(conv.num)}>
                <div style={styles.cardHeaderLeft}>
                  <span style={{ color: borderColor, marginRight: '8px', fontWeight: 700 }}>
                    {conv.status === 'DONE' ? '✓' : conv.num}
                  </span>
                  <span style={styles.cardTitle}>{conv.title}</span>
                  <span style={styles.eventCount}>{convEvents.length} events</span>
                </div>
                <div style={styles.cardHeaderRight}>
                  <span style={{ ...styles.statusBadge, color: borderColor }}>{conv.status}</span>
                  <span style={styles.chevron}>{isExpanded ? '▼' : '▶'}</span>
                </div>
              </button>

              {isExpanded && (
                <div style={styles.eventLog}>
                  {convEvents.length === 0 ? (
                    <div style={styles.noEvents}>No events for this conversation</div>
                  ) : (
                    convEvents.map((ev, i) => (
                      <div key={i} style={styles.eventRow}>
                        <span style={styles.eventType}>{ev.type}</span>
                        {ev.agent && <span style={styles.eventAgent}>{ev.agent}</span>}
                        {ev.result && <span style={styles.eventResult}>{ev.result}</span>}
                        {ev.to && <span style={styles.eventResult}>→ {ev.to}</span>}
                        {ev.cost_usd !== undefined && (
                          <span style={styles.eventCost}>${ev.cost_usd.toFixed(4)}</span>
                        )}
                        <span style={styles.eventTime}>{ev.timestamp ?? ev.ts ?? ''}</span>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: '#1e1e2e',
    overflowY: 'auto',
    height: '100%'
  },
  placeholder: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#6c7086',
    fontSize: '15px',
    marginTop: '80px'
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '16px 24px',
    borderBottom: '1px solid #313244',
    flexShrink: 0
  },
  planName: {
    fontSize: '16px',
    fontWeight: 600,
    color: '#cdd6f4'
  },
  fsmBadge: {
    fontSize: '12px',
    fontWeight: 700,
    color: '#1e1e2e',
    padding: '2px 10px',
    borderRadius: '12px'
  },
  cardList: {
    padding: '16px 24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '10px'
  },
  card: {
    borderRadius: '6px',
    overflow: 'hidden'
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: '100%',
    background: 'none',
    border: 'none',
    color: '#cdd6f4',
    cursor: 'pointer',
    padding: '10px 14px',
    textAlign: 'left'
  },
  cardHeaderLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    flex: 1,
    overflow: 'hidden'
  },
  cardTitle: {
    fontSize: '14px',
    color: '#cdd6f4',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    flex: 1
  },
  eventCount: {
    fontSize: '11px',
    color: '#6c7086',
    flexShrink: 0,
    marginLeft: '8px'
  },
  cardHeaderRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    flexShrink: 0
  },
  statusBadge: {
    fontSize: '11px',
    fontWeight: 600,
    textTransform: 'uppercase' as const
  },
  chevron: {
    fontSize: '10px',
    color: '#6c7086'
  },
  eventLog: {
    padding: '0 14px 10px 14px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px'
  },
  noEvents: {
    fontSize: '12px',
    color: '#6c7086',
    fontStyle: 'italic'
  },
  eventRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    fontSize: '12px',
    fontFamily: 'monospace',
    color: '#a6adc8',
    padding: '2px 0'
  },
  eventType: {
    color: '#89b4fa',
    fontWeight: 600,
    flexShrink: 0
  },
  eventAgent: {
    color: '#cba6f7',
    flexShrink: 0
  },
  eventResult: {
    color: '#a6e3a1',
    flexShrink: 0
  },
  eventCost: {
    color: '#f9e2af',
    flexShrink: 0
  },
  eventTime: {
    color: '#6c7086',
    fontSize: '11px',
    marginLeft: 'auto'
  }
}
