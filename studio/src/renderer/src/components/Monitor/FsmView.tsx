import { useEffect, useRef, useMemo } from 'react'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import { Tooltip } from '../ui/Tooltip'
import { useInjectCSS } from './utils'

const COMPLETED_GREEN = '#16A34A'
const ACTIVE_CYAN = '#06B6D4'
const RETRY_AMBER = '#F59E0B'

const PULSE_CSS = `
@keyframes pathly-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
@keyframes pathly-pulse-border {
  0%, 100% { border-left-color: #22D3EE; }
  50% { border-left-color: rgba(34,211,238,0.15); }
}
@keyframes pathly-dot-arrive-v2 {
  0%, 100% { box-shadow: inset 0 0 0 3px #06B6D4; }
  50%       { box-shadow: inset 0 0 0 3px rgba(6,182,212,0.25); }
}
@keyframes pathly-retry-ring {
  0%, 100% { box-shadow: inset 0 0 0 3px #F59E0B; }
  50%       { box-shadow: inset 0 0 0 3px rgba(245,158,11,0.2); }
}
.pathly-pulse { animation: none; }
.pathly-pulse-border { animation: none; }
.pathly-stepper-active { }
.pathly-stepper-retry { }
@media (prefers-reduced-motion: no-preference) {
  .pathly-pulse { animation: pathly-pulse 600ms ease-in-out 2; }
  .pathly-pulse-border { animation: pathly-pulse-border 600ms ease-in-out 2; }
  .pathly-stepper-active { animation: pathly-dot-arrive-v2 500ms ease-in-out 2; }
  .pathly-stepper-retry { animation: pathly-retry-ring 700ms ease-in-out 3; }
}
@media (prefers-reduced-motion: reduce) {
  .pathly-pulse { animation: none; }
  .pathly-pulse-border { animation: none; }
  .pathly-stepper-active { animation: none; }
  .pathly-stepper-retry { animation: none; }
}
`

type StepStatus = 'completed' | 'active' | 'active-retry' | 'pending'

function TimelineDot({ status, currentState }: { status: StepStatus; currentState: string }): JSX.Element {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (status === 'active') {
      el.classList.add('pathly-stepper-active')
      const onEnd = (): void => el.classList.remove('pathly-stepper-active')
      el.addEventListener('animationend', onEnd, { once: true })
      return () => el.removeEventListener('animationend', onEnd)
    }
    if (status === 'active-retry') {
      el.classList.add('pathly-stepper-retry')
      const onEnd = (): void => el.classList.remove('pathly-stepper-retry')
      el.addEventListener('animationend', onEnd, { once: true })
      return () => el.removeEventListener('animationend', onEnd)
    }
  }, [currentState, status])

  const base: React.CSSProperties = { width: 12, height: 12, borderRadius: '50%', flexShrink: 0 }
  const style: React.CSSProperties =
    status === 'completed'    ? { ...base, backgroundColor: COMPLETED_GREEN }
    : status === 'active'     ? { ...base, backgroundColor: 'transparent', border: `2px solid ${ACTIVE_CYAN}`, boxShadow: `inset 0 0 0 3px ${ACTIVE_CYAN}` }
    : status === 'active-retry' ? { ...base, backgroundColor: 'transparent', border: `2px dashed ${RETRY_AMBER}`, boxShadow: `inset 0 0 0 3px ${RETRY_AMBER}` }
    : { ...base, backgroundColor: 'transparent', border: '1px solid #374151' }

  return <div ref={ref} style={style} />
}

export function FsmView(): JSX.Element {
  const fsmState = useStore((s) => s.fsmState)
  const pipelineStates = useStore((s) => s.pipelineStates)
  const events = useStore((s) => s.events)
  const t = useTheme()

  useInjectCSS(PULSE_CSS)

  const PIPELINE = useMemo(
    () => (pipelineStates.length > 0 ? pipelineStates : ['STORMING', 'PLANNING', 'BUILDING', 'REVIEWING', 'DONE'])
      .map((s) => s.replace(/^[-\s]+/, '').trim()),
    [pipelineStates]
  )

  // Count how many times each stage was re-entered via a backward transition
  const retryMap = useMemo(() => {
    const map: Record<string, number> = {}
    for (const ev of events) {
      if (ev.type === 'STATE_TRANSITION' && ev.from && ev.to) {
        const from = String(ev.from).toUpperCase()
        const to = String(ev.to).toUpperCase()
        const fromIdx = PIPELINE.indexOf(from)
        const toIdx = PIPELINE.indexOf(to)
        if (fromIdx > toIdx && toIdx >= 0) {
          map[to] = (map[to] ?? 0) + 1
        }
      }
    }
    return map
  }, [events, PIPELINE])

  const activeState = fsmState?.current ?? null
  const isIdleOrNull = !activeState || activeState === 'IDLE'
  const activeIdx = isIdleOrNull ? -1 : PIPELINE.indexOf(activeState)

  const flow = fsmState?.flow
  const isDebugOrExplore = flow === 'debug' || flow === 'explore'
  const convLabel = isDebugOrExplore ? 'cycle' : 'conv'
  const convNum = fsmState?.conv ?? fsmState?.current_conversation
  const doneCount = activeIdx >= 0 ? activeIdx : 0
  const remainingCount = activeIdx >= 0 ? PIPELINE.length - activeIdx - 1 : PIPELINE.length

  return (
    <div style={{ padding: '10px 12px 8px', flexShrink: 0, backgroundColor: t.bgMantle, borderBottom: `1px solid ${t.bgSurface1}` }}>
      {/* Conv label */}
      <div
        aria-live="polite"
        aria-atomic={true}
        style={{ fontSize: '11px', fontFamily: t.fontFamilyMono, color: t.textMuted, marginBottom: '8px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
      >
        {convNum != null
          ? `${convLabel} ${convNum} · ${doneCount} done · ${remainingCount} remaining`
          : `${doneCount} done · ${remainingCount} remaining`}
      </div>

      {/* Horizontal timeline */}
      <div
        role="group"
        aria-label={`Pipeline: ${activeState ?? 'idle'}, step ${activeIdx + 1} of ${PIPELINE.length}`}
        style={{ display: 'flex', alignItems: 'flex-start', width: '100%', overflow: 'hidden' }}
      >
        {PIPELINE.map((state, idx) => {
          const isRetried = (retryMap[state] ?? 0) > 0
          const status: StepStatus = isIdleOrNull ? 'pending'
            : idx < activeIdx ? 'completed'
            : idx === activeIdx ? (isRetried ? 'active-retry' : 'active')
            : 'pending'
          const isLast = idx === PIPELINE.length - 1
          const labelColor = status === 'active' ? t.textPrimary
            : status === 'active-retry' ? RETRY_AMBER
            : t.textMuted
          const retryCount = retryMap[state] ?? 0
          const tooltipLabel = status === 'active-retry'
            ? `${state} — retried ${retryCount}×`
            : `${state} — ${status}`

          return (
            <div key={state} style={{ display: 'flex', alignItems: 'flex-start', flex: isLast ? '0 0 auto' : 1, minWidth: 0 }}>
              {/* Dot + label column */}
              <Tooltip label={tooltipLabel} placement="bottom" delay={200}>
                <div
                  aria-label={tooltipLabel}
                  style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0, cursor: 'default' }}
                >
                  <TimelineDot status={status} currentState={activeState ?? ''} />
                  <span style={{
                    fontSize: '9px',
                    color: labelColor,
                    marginTop: '3px',
                    textTransform: 'uppercase',
                    letterSpacing: '0.03em',
                    maxWidth: '34px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    textAlign: 'center',
                    fontFamily: t.fontFamilyMono,
                    fontWeight: (status === 'active' || status === 'active-retry') ? 600 : 400,
                  }}>
                    {state.slice(0, 8)}
                  </span>
                  {status === 'active-retry' && retryCount > 0 && (
                    <span style={{
                      fontSize: '8px',
                      color: RETRY_AMBER,
                      fontFamily: t.fontFamilyMono,
                      marginTop: '1px',
                      lineHeight: 1,
                    }}>
                      ↩{retryCount}
                    </span>
                  )}
                </div>
              </Tooltip>

              {/* Connector line (not after last dot) */}
              {!isLast && (
                <div style={{
                  flex: 1,
                  height: '1px',
                  marginTop: '5px',
                  backgroundColor: idx < activeIdx ? COMPLETED_GREEN : t.bgSurface1,
                  minWidth: '4px',
                }} />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
