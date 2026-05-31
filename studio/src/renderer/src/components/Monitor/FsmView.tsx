import { useEffect, useRef, useMemo } from 'react'
import { useStore } from '../../store'
import { Tooltip } from '../ui/Tooltip'
import { useInjectCSS } from './utils'
import styles from './Monitor.module.css'

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

function dotClass(status: StepStatus): string {
  const map: Record<StepStatus, string> = {
    completed:    styles.fsmDotCompleted,
    active:       styles.fsmDotActive,
    'active-retry': styles.fsmDotRetry,
    pending:      styles.fsmDotPending,
  }
  return map[status]
}

function labelClass(status: StepStatus): string {
  if (status === 'active')       return styles.fsmStepLabelActive
  if (status === 'active-retry') return styles.fsmStepLabelRetry
  return styles.fsmStepLabelMuted
}

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

  return <div ref={ref} className={`${styles.fsmDot} ${dotClass(status)}`} />
}

export function FsmView(): JSX.Element {
  const fsmState = useStore((s) => s.fsmState)
  const pipelineStates = useStore((s) => s.pipelineStates)
  const events = useStore((s) => s.events)
  const convLabelRef = useRef<HTMLDivElement>(null)

  useInjectCSS(PULSE_CSS)

  // Set aria-atomic imperatively to avoid JSX expression lint false-positive
  useEffect(() => {
    convLabelRef.current?.setAttribute('aria-atomic', 'true')
  }, [])

  const PIPELINE = useMemo(
    () => (pipelineStates.length > 0 ? pipelineStates : ['STORMING', 'PLANNING', 'BUILDING', 'REVIEWING', 'DONE'])
      .map((s) => s.replace(/^[-\s]+/, '').trim()),
    [pipelineStates]
  )

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
    <div className={styles.fsmRoot}>
      <div ref={convLabelRef} aria-live="polite" className={styles.fsmConvLabel}>
        {convNum != null
          ? `${convLabel} ${convNum} · ${doneCount} done · ${remainingCount} remaining`
          : `${doneCount} done · ${remainingCount} remaining`}
      </div>

      <div
        role="group"
        aria-label={`Pipeline: ${activeState ?? 'idle'}, step ${activeIdx + 1} of ${PIPELINE.length}`}
        className={styles.fsmTimeline}
      >
        {PIPELINE.map((state, idx) => {
          const isRetried = (retryMap[state] ?? 0) > 0
          const status: StepStatus = isIdleOrNull ? 'pending'
            : idx < activeIdx ? 'completed'
            : idx === activeIdx ? (isRetried ? 'active-retry' : 'active')
            : 'pending'
          const isLast = idx === PIPELINE.length - 1
          const retryCount = retryMap[state] ?? 0
          const tooltipLabel = status === 'active-retry'
            ? `${state} — retried ${retryCount}×`
            : `${state} — ${status}`

          return (
            <div key={state} className={isLast ? styles.fsmStepLast : styles.fsmStep}>
              <Tooltip label={tooltipLabel} placement="bottom" delay={200}>
                <div aria-label={tooltipLabel} className={styles.fsmDotCol}>
                  <TimelineDot status={status} currentState={activeState ?? ''} />
                  <span className={`${styles.fsmStepLabel} ${labelClass(status)}`}>
                    {state.slice(0, 8)}
                  </span>
                  {status === 'active-retry' && retryCount > 0 && (
                    <span className={styles.fsmRetryBadge}>↩{retryCount}</span>
                  )}
                </div>
              </Tooltip>

              {!isLast && (
                <div className={`${styles.fsmConnector} ${idx < activeIdx ? styles.fsmConnectorDone : ''}`} />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
