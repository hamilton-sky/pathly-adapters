import { useState } from 'react'
import { useRunnerStore } from '../../../store/runnerStore'
import { AbortConfirmStrip } from './AbortConfirmStrip'
import { ReroutePopover } from './ReroutePopover'
import styles from './FlowControlBar.module.css'

const RUNNER_BASE = 'http://127.0.0.1:8765'

type Action = 'start' | 'pause' | 'resume' | 'advance' | 'retry'

export function FlowControlBar(): JSX.Element {
  const status = useRunnerStore((s) => s.status)
  const setRunnerState = useRunnerStore((s) => s.setRunnerState)
  const [showAbort, setShowAbort] = useState(false)
  const [showReroute, setShowReroute] = useState(false)

  async function postAction(action: Action): Promise<void> {
    try {
      const res = await fetch(`${RUNNER_BASE}/runner/${action}`, { method: 'POST' })
      if (!res.ok) setRunnerState({ errorMessage: `${action} failed: ${res.status}` })
    } catch {
      setRunnerState({ errorMessage: `${action} failed: network error` })
    }
  }

  const startEnabled = status === 'idle'
  const pauseEnabled = status === 'running'
  const resumeEnabled = status === 'paused'
  const advanceEnabled = status === 'blocked'
  const rerouteEnabled = status === 'blocked'
  const retryEnabled = status === 'blocked'
  const abortEnabled = status !== 'idle'

  return (
    <div className={styles.wrapper}>
      <div className={styles.bar}>
        <button
          type="button"
          className={`${styles.btn} ${!startEnabled ? styles.btnDisabled : ''}`}
          disabled={!startEnabled}
          aria-label="Start run"
          {...(startEnabled ? { 'aria-disabled': 'false' } : { 'aria-disabled': 'true' })}
          onClick={() => { void postAction('start') }}
        >
          Start
        </button>
        <button
          type="button"
          className={`${styles.btn} ${!pauseEnabled ? styles.btnDisabled : ''}`}
          disabled={!pauseEnabled}
          aria-label="Pause run"
          {...(pauseEnabled ? { 'aria-disabled': 'false' } : { 'aria-disabled': 'true' })}
          onClick={() => { void postAction('pause') }}
        >
          Pause
        </button>
        <button
          type="button"
          className={`${styles.btn} ${!resumeEnabled ? styles.btnDisabled : ''}`}
          disabled={!resumeEnabled}
          aria-label="Resume run"
          {...(resumeEnabled ? { 'aria-disabled': 'false' } : { 'aria-disabled': 'true' })}
          onClick={() => { void postAction('resume') }}
        >
          Resume
        </button>
        <button
          type="button"
          className={`${styles.btn} ${!advanceEnabled ? styles.btnDisabled : ''}`}
          disabled={!advanceEnabled}
          aria-label="Advance past decision"
          {...(advanceEnabled ? { 'aria-disabled': 'false' } : { 'aria-disabled': 'true' })}
          onClick={() => { void postAction('advance') }}
        >
          Advance
        </button>
        <div className={styles.rerouteWrapper}>
          <button
            type="button"
            className={`${styles.btn} ${!rerouteEnabled ? styles.btnDisabled : ''}`}
            disabled={!rerouteEnabled}
            aria-label="Reroute to different adapter"
            {...(rerouteEnabled ? { 'aria-disabled': 'false' } : { 'aria-disabled': 'true' })}
            onClick={() => setShowReroute((v) => !v)}
          >
            Reroute
          </button>
          {showReroute && rerouteEnabled && (
            <ReroutePopover
              onClose={() => setShowReroute(false)}
              onError={(msg) => setRunnerState({ errorMessage: msg })}
            />
          )}
        </div>
        <button
          type="button"
          className={`${styles.btn} ${!retryEnabled ? styles.btnDisabled : ''}`}
          disabled={!retryEnabled}
          aria-label="Retry after error"
          {...(retryEnabled ? { 'aria-disabled': 'false' } : { 'aria-disabled': 'true' })}
          onClick={() => { void postAction('retry') }}
        >
          Retry
        </button>
        <button
          type="button"
          className={`${styles.btn} ${styles.btnAbort} ${!abortEnabled ? styles.btnDisabled : ''}`}
          disabled={!abortEnabled}
          aria-label="Abort run"
          {...(abortEnabled ? { 'aria-disabled': 'false' } : { 'aria-disabled': 'true' })}
          onClick={() => setShowAbort((v) => !v)}
        >
          Abort
        </button>
      </div>
      {showAbort && (
        <AbortConfirmStrip
          onDone={() => setShowAbort(false)}
          onCancel={() => setShowAbort(false)}
          onError={(msg) => setRunnerState({ errorMessage: msg })}
        />
      )}
    </div>
  )
}
