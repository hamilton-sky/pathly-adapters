import { useState } from 'react'
import type { RunDetailRun } from '../types'
import { RerouteMenu } from './RerouteMenu/RerouteMenu'
import { useRunControls } from './hooks/useRunControls'
import { visibleFlowActions } from './runControlsUtils'
import s from './RunControls.module.css'

const ACTIVE_STATUS = new Set(['running', 'paused', 'awaiting_decision'])

interface Props {
  runId: string
  run: RunDetailRun | null
  onRefresh: () => void
}

// Capability-gated header controls for RunDetailPage (unified-control-plane T2): the ■ Stop
// (any active run, via apiStopRun) plus, for a flow-kind run only, the run_id-addressed
// pause/resume/advance/reroute/retry actions (POST /runs/<id>/<action>) — gated by run.status
// via visibleFlowActions so a button never appears for a call the server would reject
// (single/loop/other kinds only ever see Stop; that's ALSO how they abort — the server's
// board-lock resolver only supports 'abort', which apiStopRun already covers).
export function RunControls({ runId, run, onRefresh }: Props): JSX.Element {
  const [rerouteOpen, setRerouteOpen] = useState(false)
  const isActive = run ? ACTIVE_STATUS.has(run.status) : false
  const flowActions = run?.kind === 'flow' ? visibleFlowActions(run.status) : []
  const { pending, runStop, runPause, runResume, runAdvance, runReroute, runRetry } =
    useRunControls(runId, run, onRefresh)
  const busy = pending !== null

  return (
    <>
      {flowActions.includes('pause') && (
        <button type="button" className={s.action} disabled={busy} onClick={() => void runPause()}>
          {pending === 'pause' ? '…' : '⏸ Pause'}
        </button>
      )}
      {flowActions.includes('resume') && (
        <button type="button" className={s.action} disabled={busy} onClick={() => void runResume()}>
          {pending === 'resume' ? '…' : '▶ Resume'}
        </button>
      )}
      {flowActions.includes('advance') && (
        <button type="button" className={s.action} disabled={busy} onClick={() => void runAdvance()}>
          {pending === 'advance' ? '…' : '⏭ Advance'}
        </button>
      )}
      {flowActions.includes('reroute') && (
        <div className={s.rerouteWrap}>
          <button
            type="button"
            className={s.action}
            disabled={busy}
            {...(rerouteOpen ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
            onClick={() => setRerouteOpen((v) => !v)}
          >
            {pending === 'reroute' ? '…' : '⇄ Reroute'}
          </button>
          {rerouteOpen && (
            <RerouteMenu
              onConfirm={(adapter) => {
                setRerouteOpen(false)
                void runReroute(adapter)
              }}
              onCancel={() => setRerouteOpen(false)}
            />
          )}
        </div>
      )}
      {flowActions.includes('retry') && (
        <button type="button" className={s.action} disabled={busy} onClick={() => void runRetry()}>
          {pending === 'retry' ? '…' : '↻ Retry'}
        </button>
      )}
      {isActive && (
        <button
          type="button"
          className={`${s.action} ${s.stop}`}
          disabled={busy}
          onClick={() => void runStop()}
        >
          {pending === 'stop' ? '…' : '■ Stop'}
        </button>
      )}
    </>
  )
}
