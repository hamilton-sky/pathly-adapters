import { useEffect, useRef } from 'react'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'


const PULSE_CSS = `
@keyframes pathly-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.pathly-pulse { animation: pathly-pulse 1.5s ease-in-out infinite; }
`

export function FsmView(): JSX.Element {
  const fsmState = useStore((s) => s.fsmState)
  const pipelineStates = useStore((s) => s.pipelineStates)
  const PIPELINE = pipelineStates.length > 0
    ? pipelineStates
    : ['STORMING', 'PLANNING', 'BUILDING', 'REVIEWING', 'DONE']
  const t = useTheme()
  const styleInjectedRef = useRef(false)

  useEffect(() => {
    if (styleInjectedRef.current) return
    styleInjectedRef.current = true
    const style = document.createElement('style')
    style.textContent = PULSE_CSS
    document.head.appendChild(style)
  }, [])

  const activeState = fsmState?.state ?? null
  const isIdleOrNull = !activeState || activeState === 'IDLE'
  const activeIdx = isIdleOrNull ? -1 : PIPELINE.indexOf(activeState)

  function getStateStyle(state: string, idx: number): React.CSSProperties {
    if (isIdleOrNull) {
      return {
        padding: '6px 12px',
        borderRadius: '4px',
        border: `1px solid ${t.bgSurface0}`,
        fontSize: '13px',
        color: t.textMuted,
        backgroundColor: t.bgMantle
      }
    }
    if (idx < activeIdx) {
      return {
        padding: '6px 12px',
        borderRadius: '4px',
        border: `1px solid ${t.green}`,
        fontSize: '13px',
        color: t.green,
        opacity: 0.7,
        backgroundColor: t.bgMantle
      }
    }
    if (idx === activeIdx) {
      return {
        padding: '6px 12px',
        borderRadius: '4px',
        border: `1px solid ${t.blue}`,
        fontSize: '13px',
        color: t.blue,
        fontWeight: 600,
        backgroundColor: t.bgBase,
        display: 'flex',
        alignItems: 'center',
        gap: '6px'
      }
    }
    return {
      padding: '6px 12px',
      borderRadius: '4px',
      border: `1px solid ${t.bgSurface0}`,
      fontSize: '13px',
      color: t.textMuted,
      backgroundColor: t.bgMantle
    }
  }

  const isActive = !isIdleOrNull && activeState !== 'DONE'
  const isDone = activeState === 'DONE'

  let statusLine: React.ReactNode
  if (isActive) {
    statusLine = (
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: t.green }}>
        <span className="pathly-pulse" style={{ color: t.green }}>●</span>
        System active — {activeState}
      </div>
    )
  } else if (isDone) {
    statusLine = (
      <div style={{ fontSize: '13px', color: t.green }}>✓ Complete</div>
    )
  } else {
    statusLine = (
      <div style={{ fontSize: '13px', color: t.textMuted }}>— Idle</div>
    )
  }

  return (
    <div style={{ padding: '16px' }}>
      <div style={{
        fontSize: '13px',
        fontWeight: 600,
        color: t.textMuted,
        marginBottom: '12px',
        textTransform: 'uppercase',
        letterSpacing: '0.05em'
      }}>
        Pipeline
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center', marginBottom: '12px' }}>
        {PIPELINE.map((state, idx) => {
          const stateStyle = getStateStyle(state, idx)
          const isCurrentActive = idx === activeIdx && !isIdleOrNull

          if (idx < activeIdx && !isIdleOrNull) {
            return (
              <div key={state} style={stateStyle}>
                ✓ {state}
              </div>
            )
          }
          if (isCurrentActive) {
            return (
              <div key={state} style={stateStyle}>
                {state !== 'DONE' && (
                  <span className="pathly-pulse" style={{ color: t.green, fontSize: '10px' }}>●</span>
                )}
                {state}
              </div>
            )
          }
          return (
            <div key={state} style={stateStyle}>
              {isIdleOrNull || idx > activeIdx ? state.toLowerCase() : state}
            </div>
          )
        })}
      </div>
      {statusLine}
    </div>
  )
}
