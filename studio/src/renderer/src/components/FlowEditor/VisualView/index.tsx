import { useEffect, useRef, useState } from 'react'
import { ReactFlowProvider } from 'reactflow'
import { useStore } from '../../../store'
import { useTheme } from '../../../useTheme'
import { Z } from '../zIndex'
import type { FlowYaml } from '../../../types'
import { VisualViewInner } from './VisualViewInner'

export interface VisualViewProps {
  data: FlowYaml
  onChange: (updated: FlowYaml) => void
  onSave: () => void
  tab: 'visual' | 'yaml'
  onTabClick: (t: 'visual' | 'yaml') => void
}

function RunningBanner({ flowName, stateName }: { flowName: string; stateName: string }): JSX.Element {
  const t = useTheme()
  const { setActivePanel } = useStore()
  const [dismissed, setDismissed] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  function startTimer(): void {
    timerRef.current = setTimeout(() => setDismissed(true), 8000)
  }
  function clearTimer(): void {
    if (timerRef.current) clearTimeout(timerRef.current)
  }

  useEffect(() => {
    if (dismissed) return
    startTimer()
    return clearTimer
  }, [dismissed])

  useEffect(() => {
    return () => { clearTimer() }
  }, [])

  if (dismissed) return <></>

  return (
    <div
      role="status"
      aria-live="assertive"
      aria-label={`${flowName} pipeline is running in ${stateName}`}
      onMouseEnter={clearTimer}
      onMouseLeave={startTimer}
      style={{
        position: 'absolute',
        top: '12px',
        left: '50%',
        transform: 'translateX(-50%)',
        maxWidth: '520px',
        width: 'calc(100% - 48px)',
        borderRadius: '6px',
        padding: '10px 14px',
        backgroundColor: t.bgSurface1,
        border: `1px solid ${t.runtime}`,
        zIndex: Z.toast - 1,
        display: 'flex',
        alignItems: 'center',
        gap: '10px'
      }}
    >
      <span style={{ color: t.runtime, fontSize: '8px', flexShrink: 0 }} aria-hidden="true">●</span>
      <span style={{ flex: 1, fontSize: '13px', color: t.textPrimary }}>
        {flowName} is running · {stateName}
      </span>
      <button
        onClick={() => setActivePanel('monitor')}
        aria-label="View running flow in Monitor panel"
        style={{
          background: 'none',
          border: `1px solid ${t.runtime}`,
          borderRadius: '4px',
          color: t.runtime,
          cursor: 'pointer',
          fontSize: '12px',
          padding: '2px 8px',
          flexShrink: 0
        }}
      >
        View in Monitor →
      </button>
      <button
        onClick={() => setDismissed(true)}
        aria-label="Dismiss banner"
        style={{
          background: 'none',
          border: 'none',
          color: t.textMuted,
          cursor: 'pointer',
          fontSize: '14px',
          padding: '0 4px',
          flexShrink: 0
        }}
      >
        ✕
      </button>
    </div>
  )
}

function VisualViewWithBanner(props: VisualViewProps): JSX.Element {
  const { fsmState, activeFlowSessions, setActivePanel } = useStore()

  const isRunning = Boolean(
    fsmState?.current && fsmState.current !== 'IDLE' && fsmState.current !== 'DONE'
  )
  const isMultiFlow = Object.keys(activeFlowSessions).length >= 2

  // Track isRunning false→true transitions (EC-3.2)
  const prevRunningRef = useRef(isRunning)
  const [dismissedKey, setDismissedKey] = useState(0)

  useEffect(() => {
    const wasRunning = prevRunningRef.current
    prevRunningRef.current = isRunning
    if (!wasRunning && isRunning) {
      // Reset banner and auto-switch to monitor only when running starts
      setDismissedKey((k) => k + 1)
      if (isMultiFlow) setActivePanel('monitor')
    }
  }, [isRunning, isMultiFlow, setActivePanel])

  const flowName = (fsmState?.flow as string | undefined) ?? 'flow'
  const stateName = (fsmState?.current as string | undefined) ?? ''

  return (
    <div style={{ position: 'relative', flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {isRunning && !isMultiFlow && (
        <RunningBanner key={dismissedKey} flowName={flowName} stateName={stateName} />
      )}
      <VisualViewInner {...props} />
    </div>
  )
}

export function VisualView(props: VisualViewProps): JSX.Element {
  return (
    <ReactFlowProvider>
      <VisualViewWithBanner {...props} />
    </ReactFlowProvider>
  )
}
