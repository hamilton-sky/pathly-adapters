import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { readFile } from '../services/pathlyApi'
import { useTheme } from '../useTheme'
import type { Theme } from '../theme'
import type { ConvRow } from '../types'
import { parseProgressMd } from '../hooks/usePlanConversations'

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


function fsmStateColor(state: string, t: Theme): string {
  if (state === 'DONE') return t.green
  if (state === 'BUILDING' || state === 'REVIEWING') return t.blue
  if (state === 'BLOCKED') return t.red
  return t.textMuted
}

function statusBorderColor(status: string, t: Theme): string {
  if (status === 'DONE') return t.green
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING') return t.blue
  if (status === 'BLOCKED') return t.red
  return t.textMuted
}

function statusBgColor(status: string): string {
  if (status === 'DONE') return 'rgba(166,227,161,0.05)'
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING')
    return 'rgba(137,180,250,0.05)'
  if (status === 'BLOCKED') return 'rgba(243,139,168,0.05)'
  return 'rgba(108,112,134,0.05)'
}

function makeStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    container: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: t.bgBase,
      overflowY: 'auto' as const,
      height: '100%'
    },
    placeholder: {
      flex: 1,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: t.textMuted,
      fontSize: '15px',
      marginTop: '80px'
    },
    header: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '16px 24px',
      borderBottom: `1px solid ${t.bgSurface0}`,
      flexShrink: 0
    },
    planName: {
      fontSize: '16px',
      fontWeight: 600,
      color: t.textPrimary
    },
    fsmBadge: {
      fontSize: '12px',
      fontWeight: 700,
      color: t.bgBase,
      padding: '2px 10px',
      borderRadius: '12px'
    },
    cardList: {
      padding: '16px 24px',
      display: 'flex',
      flexDirection: 'column' as const,
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
      color: t.textPrimary,
      cursor: 'pointer',
      padding: '10px 14px',
      textAlign: 'left' as const
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
      color: t.textPrimary,
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap' as const,
      flex: 1
    },
    eventCount: {
      fontSize: '11px',
      color: t.textMuted,
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
      color: t.textMuted
    },
    eventLog: {
      padding: '0 14px 10px 14px',
      display: 'flex',
      flexDirection: 'column' as const,
      gap: '4px'
    },
    noEvents: {
      fontSize: '12px',
      color: t.textMuted,
      fontStyle: 'italic'
    },
    eventRow: {
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      fontSize: '12px',
      fontFamily: 'monospace',
      color: t.textSecondary,
      padding: '2px 0'
    },
    eventType: {
      color: t.blue,
      fontWeight: 600,
      flexShrink: 0
    },
    eventAgent: {
      color: t.accent,
      flexShrink: 0
    },
    eventResult: {
      color: t.green,
      flexShrink: 0
    },
    eventCost: {
      color: t.yellow,
      flexShrink: 0
    },
    eventTime: {
      color: t.textMuted,
      fontSize: '11px',
      marginLeft: 'auto'
    },
    recentEventsSection: {
      padding: '0 24px 16px 24px',
      display: 'flex',
      flexDirection: 'column' as const,
      gap: '4px'
    },
    recentEventsHeader: {
      fontSize: '12px',
      fontWeight: 600,
      color: t.textMuted,
      textTransform: 'uppercase' as const,
      letterSpacing: '0.05em',
      marginBottom: '6px'
    }
  }
}

export function PlanBoard(): JSX.Element {
  const { projectPath, activeTopic } = useStore()
  const t = useTheme()
  const styles = makeStyles(t)

  const [fsmState, setFsmState] = useState<string>('')
  const [convs, setConvs] = useState<ConvRow[]>([])
  const [events, setEvents] = useState<EventEntry[]>([])
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
      try {
        const raw = await readFile(`${base}/STATE.json`)
        const parsed = JSON.parse(raw) as { current?: string }
        setFsmState(parsed.current ?? '')
      } catch {
        setFsmState('')
      }

      try {
        const md = await readFile(`${base}/PROGRESS.md`)
        const rows = parseProgressMd(md)
        setConvs(rows)
        setNoProgress(rows.length === 0)
      } catch {
        setConvs([])
        setNoProgress(true)
      }

      try {
        const raw = await readFile(`${base}/EVENTS.jsonl`)
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
            <span style={{ ...styles.fsmBadge, backgroundColor: fsmStateColor(fsmState, t) }}>
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
          <span style={{ ...styles.fsmBadge, backgroundColor: fsmStateColor(fsmState, t) }}>
            {fsmState}
          </span>
        )}
      </div>

      <div style={styles.cardList}>
        {convs.map((conv) => {
          const borderColor = statusBorderColor(conv.status, t)
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
              <div style={styles.cardHeader}>
                <div style={styles.cardHeaderLeft}>
                  <span style={{ color: borderColor, marginRight: '8px', fontWeight: 700 }}>
                    {conv.status === 'DONE' ? '✓' : conv.num}
                  </span>
                  <span style={styles.cardTitle}>{conv.title}</span>
                </div>
                <div style={styles.cardHeaderRight}>
                  <span style={{ ...styles.statusBadge, color: borderColor }}>{conv.status}</span>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {events.length > 0 && (
        <div style={styles.recentEventsSection}>
          <div style={styles.recentEventsHeader}>Recent events</div>
          {events.map((ev, i) => (
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
          ))}
        </div>
      )}
    </div>
  )
}
