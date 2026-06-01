import { useState } from 'react'
import { Play, Pause, SkipForward, ChevronsRight, Shuffle, RotateCcw, Square } from 'lucide-react'
import { useRunnerStore } from '../../../store/runnerStore'
import { AbortConfirmStrip } from './AbortConfirmStrip'
import { ReroutePopover } from './ReroutePopover'
import { RunnerBtn } from './RunnerBtn'
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
      <div className={styles.rows}>
        {/* Row 1 — lifecycle: control the run */}
        <div className={styles.row}>
          <RunnerBtn
            label="Start"
            tooltip="Start a new pipeline run"
            enabled={startEnabled}
            onClick={() => { void postAction('start') }}
            extraClass={startEnabled ? styles.btnPrimary : ''}
          >
            <Play size={10} />
          </RunnerBtn>

          <RunnerBtn
            label="Pause"
            tooltip="Pause the running pipeline"
            enabled={pauseEnabled}
            onClick={() => { void postAction('pause') }}
          >
            <Pause size={10} />
          </RunnerBtn>

          <RunnerBtn
            label="Resume"
            tooltip="Continue from where it paused"
            enabled={resumeEnabled}
            onClick={() => { void postAction('resume') }}
          >
            <SkipForward size={10} />
          </RunnerBtn>
        </div>

        {/* Row 2 — unblock: decision actions + abort */}
        <div className={styles.row}>
          <RunnerBtn
            label="Advance"
            tooltip="Skip past the current decision point"
            enabled={advanceEnabled}
            onClick={() => { void postAction('advance') }}
            extraClass={styles.btnDecision}
          >
            <ChevronsRight size={10} />
          </RunnerBtn>

          <div className={styles.rerouteWrapper}>
            <RunnerBtn
              label="Reroute"
              tooltip="Switch to a different AI adapter mid-run"
              enabled={rerouteEnabled}
              onClick={() => setShowReroute((v) => !v)}
              extraClass={styles.btnDecision}
            >
              <Shuffle size={10} />
            </RunnerBtn>
            {showReroute && rerouteEnabled && (
              <ReroutePopover
                onClose={() => setShowReroute(false)}
                onError={(msg) => setRunnerState({ errorMessage: msg })}
              />
            )}
          </div>

          <RunnerBtn
            label="Retry"
            tooltip="Retry the current blocked stage"
            enabled={retryEnabled}
            onClick={() => { void postAction('retry') }}
            extraClass={styles.btnDecision}
          >
            <RotateCcw size={10} />
          </RunnerBtn>

          <RunnerBtn
            label="Abort"
            tooltip="Stop the run completely"
            enabled={abortEnabled}
            onClick={() => setShowAbort((v) => !v)}
            abortStyle
          >
            <Square size={10} />
          </RunnerBtn>
        </div>
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
