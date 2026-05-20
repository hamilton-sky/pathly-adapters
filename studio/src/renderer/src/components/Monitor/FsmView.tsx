import { useEffect, useRef } from 'react'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'

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

@keyframes pathly-dot-arrive-v2 {
  0%, 100% { box-shadow: inset 0 0 0 4px #06B6D4; }
  50%       { box-shadow: inset 0 0 0 4px rgba(6,182,212,0.25); }
}

/* Base: no animation (opt-in pattern) */
.pathly-pulse { animation: none; }
.pathly-pulse-border { animation: none; }
.pathly-stepper-active { /* base: no animation */ }

/* Add motion only when user has no preference */
@media (prefers-reduced-motion: no-preference) {
  .pathly-pulse { animation: pathly-pulse 600ms ease-in-out 2; }
  .pathly-pulse-border { animation: pathly-pulse-border 600ms ease-in-out 2; }
  .pathly-stepper-active { animation: pathly-dot-arrive-v2 500ms ease-in-out 2; }
}

@media (prefers-reduced-motion: reduce) {
  .pathly-pulse { animation: none; }
  .pathly-pulse-border { animation: none; }
  .pathly-stepper-active { animation: none; }
}
`

// ── Vertical pipeline stepper ────────────────────────────────────────────────

const ROW_HEIGHT = 28       // px per step item — drives rail line math
const DOT_CENTER = 14       // ROW_HEIGHT / 2 — vertical center of dot within its row

type StepStatus = 'completed' | 'active' | 'pending'

interface StepDotProps {
  status: StepStatus
  currentState: string
}

function StepDot({ status, currentState }: StepDotProps): JSX.Element {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el || status !== 'active') return
    el.classList.add('pathly-stepper-active')
    const onEnd = () => el.classList.remove('pathly-stepper-active')
    el.addEventListener('animationend', onEnd, { once: true })
    return () => el.removeEventListener('animationend', onEnd)
  }, [currentState, status])

  const base: React.CSSProperties = {
    width: 16,
    height: 16,
    borderRadius: '50%',
    flexShrink: 0,
    position: 'relative',
    zIndex: 1,
  }

  const dotStyle: React.CSSProperties =
    status === 'completed'
      ? { ...base, backgroundColor: COMPLETED_GREEN, border: 'none' }
      : status === 'active'
      ? {
          ...base,
          backgroundColor: 'transparent',
          border: `2px solid ${ACTIVE_CYAN}`,
          boxShadow: `inset 0 0 0 4px ${ACTIVE_CYAN}`,
        }
      : {
          ...base,
          backgroundColor: 'transparent',
          border: '1px solid #5a5d8a',
        }

  return <div ref={ref} style={dotStyle} />
}

// ── FsmView ───────────────────────────────────────────────────────────────────

export function FsmView(): JSX.Element {
  const fsmState = useStore((s) => s.fsmState)
  const pipelineStates = useStore((s) => s.pipelineStates)
  const PIPELINE = (pipelineStates.length > 0
    ? pipelineStates
    : ['STORMING', 'PLANNING', 'BUILDING', 'REVIEWING', 'DONE']
  ).map((s) => s.replace(/^[-\s]+/, '').trim())
  const t = useTheme()
  const styleInjectedRef = useRef(false)

  useEffect(() => {
    if (styleInjectedRef.current) return
    styleInjectedRef.current = true
    const style = document.createElement('style')
    style.textContent = PULSE_CSS
    document.head.appendChild(style)
  }, [])

  const activeState = fsmState?.current ?? null
  const isIdleOrNull = !activeState || activeState === 'IDLE'
  const activeIdx = isIdleOrNull ? -1 : PIPELINE.indexOf(activeState)

  // conv/cycle label
  const flow = fsmState?.flow
  const isDebugOrExplore = flow === 'debug' || flow === 'explore'
  const convLabel = isDebugOrExplore ? 'cycle' : 'conv'
  const convNum = fsmState?.conv ?? fsmState?.current_conversation

  // Vertical rail geometry
  const totalStates = PIPELINE.length
  const railTop = DOT_CENTER
  const splitY = activeIdx >= 0 ? activeIdx * ROW_HEIGHT + DOT_CENTER : DOT_CENTER
  const railBottom = (totalStates - 1) * ROW_HEIGHT + DOT_CENTER
  const showCompletedSegment = activeIdx > 0
  const showPendingSegment = activeIdx >= 0 && activeIdx < totalStates - 1

  const doneCount = activeIdx >= 0 ? activeIdx : 0
  const remainingCount = activeIdx >= 0 ? totalStates - activeIdx - 1 : totalStates

  const railLineBase: React.CSSProperties = {
    position: 'absolute',
    left: '19px',  // containerPaddingLeft(12) + dotRadius(8) - halfLineWidth(1) = 19px
    width: '2px',
    borderRadius: '1px',
    pointerEvents: 'none',
    zIndex: 0,
  }

  return (
    <div style={{ padding: '16px' }}>
      {/* Vertical pipeline stepper */}
      <div
        role="group"
        aria-label={`Pipeline progress: ${activeState ?? 'idle'} — step ${activeIdx + 1} of ${totalStates}`}
        style={{ display: 'flex', flexDirection: 'column', gap: 0, padding: '0 0 4px 0' }}
      >
        {/* Section header */}
        <div style={{
          fontSize: '13px',
          fontWeight: 600,
          color: t.textMuted,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          marginBottom: '8px',
        }}>
          Pipeline
        </div>

        {/* Conv/count indicator */}
        <div
          aria-live="polite"
          aria-atomic={true}
          style={{
            fontSize: '11px',
            fontFamily: t.fontFamilyMono,
            color: t.textMuted,
            letterSpacing: '0.02em',
            marginBottom: '8px',
            paddingLeft: '20px',
            whiteSpace: 'nowrap',
          }}
        >
          {convNum != null
            ? `${convLabel} ${convNum} · ${doneCount} done · ${remainingCount} remaining`
            : `${doneCount} done · ${remainingCount} remaining`}
        </div>

        {/* Step list with rail lines */}
        <ol
          role="list"
          aria-label="Pipeline states"
          style={{ listStyle: 'none', margin: 0, padding: '0 0 0 12px', position: 'relative' }}
        >
          {/* Completed rail segment */}
          {showCompletedSegment && (
            <div
              aria-hidden="true"
              style={{
                ...railLineBase,
                top: `${railTop}px`,
                height: `${splitY - railTop}px`,
                backgroundColor: COMPLETED_GREEN,
              }}
            />
          )}

          {/* Pending rail segment */}
          {showPendingSegment && (
            <div
              aria-hidden="true"
              style={{
                ...railLineBase,
                top: `${splitY}px`,
                height: `${railBottom - splitY}px`,
                backgroundColor: t.bgSurface1,
              }}
            />
          )}

          {/* When at first state: render full pending segment from first to last dot */}
          {activeIdx === 0 && totalStates > 1 && (
            <div
              aria-hidden="true"
              style={{
                ...railLineBase,
                top: `${railTop}px`,
                height: `${railBottom - railTop}px`,
                backgroundColor: t.bgSurface1,
              }}
            />
          )}

          {/* Step rows */}
          {PIPELINE.map((state, idx) => {
            const status: StepStatus =
              isIdleOrNull
                ? 'pending'
                : idx < activeIdx
                ? 'completed'
                : idx === activeIdx
                ? 'active'
                : 'pending'

            const labelStyle: React.CSSProperties =
              status === 'active'
                ? {
                    fontSize: '12px',
                    fontFamily: t.fontFamilyMono,
                    fontWeight: 600,
                    color: t.textPrimary,
                    letterSpacing: '0.04em',
                    textTransform: 'uppercase',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }
                : {
                    fontSize: '11px',
                    fontFamily: t.fontFamilyMono,
                    fontWeight: 400,
                    color: t.textMuted,
                    letterSpacing: '0.03em',
                    textTransform: 'uppercase',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }

            return (
              <li
                key={state}
                aria-label={`${state}: ${status}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  height: `${ROW_HEIGHT}px`,
                  position: 'relative',
                  zIndex: 1,
                  cursor: 'default',
                }}
              >
                <StepDot status={status} currentState={activeState ?? ''} />
                <span style={labelStyle}>{state}</span>
              </li>
            )
          })}
        </ol>
      </div>

    </div>
  )
}
