import { useEffect, useLayoutEffect, useRef, useState, memo } from 'react'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import { formatRelativeTime } from './utils'
import type { FsmEvent } from '../../types'

// Intentionally not t.green (#4ade80 lime) and not rgba — alpha on dark bg fails WCAG 3:1
const COMPLETED_GREEN = '#16A34A'
// cyan-500: data encoding only, not interactive chrome
const ACTIVE_CYAN = '#06B6D4'

const PULSE_CSS = `
@keyframes pathly-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

@keyframes pathly-pulse-border {
  0%, 100% { border-left-color: #22D3EE; }
  50% { border-left-color: rgba(34,211,238,0.15); }
}

/* Base: no animation (opt-in pattern) */
.pathly-pulse { animation: none; }
.pathly-pulse-border { animation: none; }

/* Add motion only when user has no preference */
@media (prefers-reduced-motion: no-preference) {
  .pathly-pulse { animation: pathly-pulse 600ms ease-in-out 2; }
  .pathly-pulse-border { animation: pathly-pulse-border 600ms ease-in-out 2; }
}

@media (prefers-reduced-motion: reduce) {
  .pathly-pulse { animation: none; }
  .pathly-pulse-border { animation: none; }
}
`

interface VisitRow {
  state: string
  ts: string
  status: 'completed' | 'active' | 'failed'
  agent: string | null
  conv: number | null
  isLoop: boolean
  visitCount: number
}

function buildVisitRows(events: FsmEvent[], PIPELINE: string[], activeState: string | null): VisitRow[] {
  const transitions = events
    .filter((e) => e.type === 'STATE_TRANSITION' && e.ts)
    .sort((a, b) => {
      const ta = new Date(a.ts!).getTime()
      const tb = new Date(b.ts!).getTime()
      return ta - tb
    })

  const rows: VisitRow[] = []
  const visitCounts: Record<string, number> = {}

  for (let i = 0; i < transitions.length; i++) {
    const ev = transitions[i]
    const stateName = (ev.to ?? ev.from ?? '') as string
    if (!stateName) continue

    visitCounts[stateName] = (visitCounts[stateName] ?? 0) + 1
    const visitCount = visitCounts[stateName]
    const isLoop = visitCount > 1

    // Find agent: first AGENT_SPAWNED with ts > this transition's ts
    const agent = events.find(
      (e) => e.type === 'AGENT_SPAWNED' && e.ts && e.ts > ev.ts!
    )?.agent ?? null

    const conv = ev.conversation ?? null

    // Failure detection: if next transition goes backward in pipeline, this visit failed
    let status: 'completed' | 'active' | 'failed' = 'completed'
    const nextTransition = transitions[i + 1]
    if (nextTransition) {
      const thisIdx = PIPELINE.indexOf(stateName)
      const nextIdx = PIPELINE.indexOf((nextTransition.to ?? '') as string)
      if (thisIdx >= 0 && nextIdx >= 0 && nextIdx < thisIdx) {
        status = 'failed'
      }
    } else {
      // Last transition — check if still active
      if (stateName === activeState) {
        status = 'active'
      }
    }

    rows.push({ state: stateName, ts: ev.ts!, status, agent, conv, isLoop, visitCount })
  }

  // Sort by ts (EC-1.1 guard)
  rows.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime())

  return rows
}

interface VisitRowProps {
  row: VisitRow
  convLabel: string
  tick: number
}

const VisitRowItem = memo(function VisitRowItem({ row, convLabel, tick }: VisitRowProps): JSX.Element {
  const t = useTheme()

  // tick is used to force re-render for timestamp refresh
  void tick

  let icon: string
  let iconColor: string
  let stateColor: string

  if (row.status === 'completed') {
    icon = '✓'
    iconColor = COMPLETED_GREEN
    stateColor = t.textSecondary
  } else if (row.status === 'active') {
    icon = '●'
    iconColor = ACTIVE_CYAN
    stateColor = t.textPrimary
  } else {
    icon = '✗'
    iconColor = t.red
    stateColor = t.textSecondary
  }

  const timeStr = formatRelativeTime(row.ts)
  const agentStr = row.agent ?? '—'
  const convStr = row.conv != null ? `${convLabel} ${row.conv}` : convLabel

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: '8px',
        padding: '2px 0',
        fontFamily: t.fontFamilyMono,
        lineHeight: '1.7',
        whiteSpace: 'pre',
      }}
    >
      <span
        className={row.status === 'active' ? 'pathly-pulse' : undefined}
        style={{ color: iconColor, fontSize: '12px', flexShrink: 0 }}
      >
        {icon}
      </span>
      <span style={{ color: stateColor, fontSize: '12px', fontWeight: row.status === 'active' ? 600 : 400, minWidth: '100px' }}>
        {row.state}
      </span>
      <span style={{ color: t.textMuted, fontSize: '11px' }}>
        {convStr}
      </span>
      <span style={{ color: t.textMuted, fontSize: '11px' }}>
        {agentStr}
      </span>
      <span style={{ color: t.textMuted, fontSize: '11px' }}>
        {timeStr}
      </span>
    </div>
  )
})

export function FsmView(): JSX.Element {
  const fsmState = useStore((s) => s.fsmState)
  const pipelineStates = useStore((s) => s.pipelineStates)
  const events = useStore((s) => s.events)
  const PIPELINE = (pipelineStates.length > 0
    ? pipelineStates
    : ['STORMING', 'PLANNING', 'BUILDING', 'REVIEWING', 'DONE']
  ).map((s) => s.replace(/^[-\s]+/, '').trim())
  const t = useTheme()
  const styleInjectedRef = useRef(false)

  // Reduced motion state — subscribe to runtime changes
  const [reducedMotion, setReducedMotion] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  useEffect(() => {
    if (styleInjectedRef.current) return
    styleInjectedRef.current = true
    const style = document.createElement('style')
    style.textContent = PULSE_CSS
    document.head.appendChild(style)
  }, [])

  // Timestamp refresh tick (30s)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), 30_000)
    return () => clearInterval(id)
  }, [])

  const activeState = fsmState?.current ?? null
  const isIdleOrNull = !activeState || activeState === 'IDLE'
  const activeIdx = isIdleOrNull ? -1 : PIPELINE.indexOf(activeState)

  // Rail width measurement for sliding dot
  const railContainerRef = useRef<HTMLDivElement>(null)
  const [railWidth, setRailWidth] = useState(0)
  const [dotReady, setDotReady] = useState(false)

  useLayoutEffect(() => {
    const el = railContainerRef.current
    if (!el) return

    const measure = () => {
      const w = el.getBoundingClientRect().width
      setRailWidth(w)
    }

    // Initial synchronous measurement before ResizeObserver fires
    measure()

    // One rAF to avoid paint-before-transition flash
    requestAnimationFrame(() => {
      setDotReady(true)
    })

    const ro = new ResizeObserver(() => {
      requestAnimationFrame(measure)
    })
    ro.observe(el)

    return () => ro.disconnect()
  }, [])

  // Compute sliding dot offset
  const total = PIPELINE.length
  const dotOffsetPx = (() => {
    if (activeIdx < 0 || total <= 1 || railWidth === 0) return 0
    // dot centers: 16px padding + 5px half-dot + i * (width - 32px padding - 10px dot) / (n-1)
    // subtract 6 to center the 12px sliding marker
    return 15 + (activeIdx / (total - 1)) * (railWidth - 42)
  })()

  const dotTransition = reducedMotion ? 'none' : `transform ${t.transitionBase}`

  // conv/cycle label
  const flow = fsmState?.flow
  const isDebugOrExplore = flow === 'debug' || flow === 'explore'
  const convLabel = isDebugOrExplore ? 'cycle' : 'conv'
  const convNum = fsmState?.conv ?? fsmState?.current_conversation

  // Execution trace rows
  const visitRows = buildVisitRows(events, PIPELINE, activeState)

  // Trace auto-scroll
  const traceRef = useRef<HTMLDivElement>(null)
  const [userScrolled, setUserScrolled] = useState(false)

  useEffect(() => {
    if (!userScrolled && traceRef.current) {
      traceRef.current.scrollTop = traceRef.current.scrollHeight
    }
  }, [visitRows.length, userScrolled])

  const handleScroll = () => {
    const el = traceRef.current
    if (!el) return
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 8
    setUserScrolled(!isAtBottom)
  }

  // Rail line pixel positions — dot-center to dot-center, split at active dot center
  const lineStart = 21  // first dot center: 16px padding + 5px dot radius
  const lineEnd = railWidth > 0 ? railWidth - 21 : 0  // last dot center from left
  const activeDotCenter = dotOffsetPx + 6  // center of 12px sliding marker

  return (
    <div style={{ padding: '16px' }}>
      {/* Pipeline label + conv/cycle */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        marginBottom: '12px'
      }}>
        <div style={{
          fontSize: '13px',
          fontWeight: 600,
          color: t.textMuted,
          textTransform: 'uppercase',
          letterSpacing: '0.05em'
        }}>
          Pipeline
        </div>
        {convNum != null && (
          <div style={{ fontSize: '11px', color: t.textMuted }}>
            {convLabel} {convNum}
          </div>
        )}
      </div>

      {/* FSM Rail */}
      <div
        ref={railContainerRef}
        role="progressbar"
        aria-valuenow={activeIdx >= 0 ? activeIdx : 0}
        aria-valuemin={0}
        aria-valuemax={total - 1}
        aria-label={`Pipeline progress: ${activeState ?? 'idle'} — step ${activeIdx + 1} of ${total}`}
        style={{
          display: 'flex',
          alignItems: 'center',
          position: 'relative',
          padding: '20px 16px 8px 16px',
          gap: 0,
          marginBottom: '4px',
        }}
      >
        {/* Done rail segment — pixel-exact, dot-center to active dot-center */}
        {dotReady && activeIdx > 0 && (
          <div
            aria-hidden="true"
            style={{
              position: 'absolute',
              top: '50%',
              left: `${lineStart}px`,
              width: `${activeDotCenter - lineStart}px`,
              height: '2px',
              borderRadius: '1px',
              backgroundColor: COMPLETED_GREEN,
              transform: 'translateY(-50%)',
              pointerEvents: 'none',
            }}
          />
        )}
        {/* Pending rail segment — active dot-center to last dot-center */}
        {dotReady && (
          <div
            aria-hidden="true"
            style={{
              position: 'absolute',
              top: '50%',
              left: `${activeIdx >= 0 ? activeDotCenter : lineStart}px`,
              width: `${lineEnd - (activeIdx >= 0 ? activeDotCenter : lineStart)}px`,
              height: '2px',
              borderRadius: '1px',
              backgroundColor: t.bgSurface1,
              transform: 'translateY(-50%)',
              pointerEvents: 'none',
            }}
          />
        )}

        {/* State dots */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            width: '100%',
            position: 'relative',
            zIndex: 1,
          }}
        >
          {PIPELINE.map((state, idx) => {
            const isCompleted = !isIdleOrNull && idx < activeIdx
            const isCurrent = !isIdleOrNull && idx === activeIdx
            const dotStyle: React.CSSProperties = isCompleted
              ? {
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  backgroundColor: COMPLETED_GREEN,
                  border: 'none',
                  flexShrink: 0,
                }
              : isCurrent
              ? {
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  backgroundColor: 'transparent',
                  border: `1px solid ${t.textMuted}`,
                  flexShrink: 0,
                  // sliding marker (zIndex:2) is the sole active indicator
                }
              : {
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  backgroundColor: 'transparent',
                  border: `1px solid ${t.textMuted}`,
                  flexShrink: 0,
                }

            const labelColor = isCompleted
              ? COMPLETED_GREEN
              : isCurrent
              ? t.textPrimary
              : t.textMuted

            // Compact mode: for 7+ state pipelines, only show the active label
            const showLabel = PIPELINE.length <= 6 || isCurrent

            return (
              <div
                key={state}
                style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}
              >
                <div
                  role="img"
                  aria-label={`${state}: ${isCompleted ? 'completed' : isCurrent ? 'active' : 'pending'}`}
                  style={dotStyle}
                />
                {showLabel && (
                  <div style={{
                    fontSize: '10px',
                    fontFamily: t.fontFamilyBase,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    marginTop: '6px',
                    textAlign: 'center',
                    maxWidth: '64px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    color: labelColor,
                    fontWeight: isCurrent ? 600 : 400,
                  }}>
                    {state}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Count line for compact mode (7+ states) */}
        {PIPELINE.length > 6 && activeIdx >= 0 && (
          <div
            aria-hidden="true"
            style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              fontSize: '10px',
              color: t.textMuted,
              textAlign: 'center',
              letterSpacing: '0.02em',
            }}
          >
            {activeIdx} done · {PIPELINE.length - activeIdx - 1} remaining
          </div>
        )}

        {/* Sliding active marker */}
        {!isIdleOrNull && dotReady && (
          <div
            aria-hidden="true"
            style={{
              position: 'absolute',
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              backgroundColor: ACTIVE_CYAN,
              top: '50%',
              left: 0,
              transform: `translateX(${dotOffsetPx}px) translateY(-50%)`,
              transition: dotTransition,
              pointerEvents: 'none',
              zIndex: 2,
            }}
          />
        )}
      </div>

      {/* Execution trace */}
      <div style={{ marginTop: '16px' }}>
        <div style={{
          fontSize: '11px',
          fontWeight: 600,
          color: t.textMuted,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          marginBottom: '6px',
        }}>
          Execution Trace
        </div>

        {/* role="log" must be present on initial render per W3C ARIA23 */}
        <div
          role="log"
          aria-label="Execution trace"
          aria-live="polite"
          aria-atomic={false}
          tabIndex={0}
          ref={traceRef}
          onScroll={handleScroll}
          style={{
            maxHeight: '200px',
            overflowY: 'auto',
            padding: '6px 0',
            outline: 'none',
          }}
        >
          {visitRows.length === 0 ? (
            <div style={{
              color: t.textMuted,
              fontSize: '13px',
              textAlign: 'center',
              padding: '8px 0',
            }}>
              Waiting for flow activity.
            </div>
          ) : (
            visitRows.map((row, i) => (
              <VisitRowItem
                key={`${row.state}-${row.ts}-${i}`}
                row={row}
                convLabel={convLabel}
                tick={tick}
              />
            ))
          )}
        </div>

        {userScrolled && (
          <div
            style={{
              color: t.textMuted,
              fontSize: '11px',
              textAlign: 'center',
              cursor: 'pointer',
              padding: '4px 0',
            }}
            onClick={() => {
              setUserScrolled(false)
              if (traceRef.current) {
                traceRef.current.scrollTop = traceRef.current.scrollHeight
              }
            }}
          >
            ↓ scroll to latest
          </div>
        )}
      </div>
    </div>
  )
}
