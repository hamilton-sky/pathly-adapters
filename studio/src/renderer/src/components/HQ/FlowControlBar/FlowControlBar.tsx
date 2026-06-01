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
  const topic = useRunnerStore((s) => s.topic)
  const setRunnerState = useRunnerStore((s) => s.setRunnerState)
  const [showAbort, setShowAbort] = useState(false)
  const [showReroute, setShowReroute] = useState(false)

  async function postAction(action: Action, extraBody: Record<string, unknown> = {}): Promise<void> {
    const { topic, projectRoot } = useRunnerStore.getState()
    const body: Record<string, unknown> = { topic, ...extraBody }
    try {
      const res = await fetch(`${RUNNER_BASE}/runner/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
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
        {/* Lifecycle group */}
        <RunnerBtn label="Start" tooltip="Start a new pipeline run" enabled={startEnabled} onClick={() => {
          const { projectRoot } = useRunnerStore.getState()
          void postAction('start', { flow: 'team', project_root: projectRoot ?? '', max_iterations: 20, max_cost_usd: 5.0 })
        }} extraClass={startEnabled ? styles.btnPrimary : ''}>
          <Play size={12} />
        </RunnerBtn>
        <RunnerBtn label="Pause" tooltip="Pause the running pipeline" enabled={pauseEnabled} onClick={() => { void postAction('pause') }}>
          <Pause size={12} />
        </RunnerBtn>
        <RunnerBtn label="Resume" tooltip="Continue from where it paused" enabled={resumeEnabled} onClick={() => { void postAction('resume') }}>
          <SkipForward size={12} />
        </RunnerBtn>

        <div className={styles.sep} />

        {/* Decision group */}
        <RunnerBtn label="Advance" tooltip="Skip past the current decision point" enabled={advanceEnabled} onClick={() => { void postAction('advance') }} extraClass={styles.btnDecision}>
          <ChevronsRight size={12} />
        </RunnerBtn>
        <div className={styles.rerouteWrapper}>
          <RunnerBtn label="Reroute" tooltip="Switch to a different AI adapter mid-run" enabled={rerouteEnabled} onClick={() => setShowReroute((v) => !v)} extraClass={styles.btnDecision}>
            <Shuffle size={12} />
          </RunnerBtn>
          {showReroute && rerouteEnabled && (
            <ReroutePopover onClose={() => setShowReroute(false)} onError={(msg) => setRunnerState({ errorMessage: msg })} />
          )}
        </div>
        <RunnerBtn label="Retry" tooltip="Retry the current blocked stage" enabled={retryEnabled} onClick={() => {
          const { projectRoot } = useRunnerStore.getState()
          void postAction('retry', { flow: 'team', project_root: projectRoot ?? '', max_iterations: 20, max_cost_usd: 5.0 })
        }} extraClass={styles.btnDecision}>
          <RotateCcw size={12} />
        </RunnerBtn>

        <div className={styles.sep} />

        {/* Abort */}
        <RunnerBtn label="Abort" tooltip="Stop the run completely" enabled={abortEnabled} onClick={() => setShowAbort((v) => !v)} abortStyle>
          <Square size={12} />
        </RunnerBtn>
      </div>

      {topic === null && (
        <div className={styles.noTopicWarning}>No active feature — use /pathly go to start one</div>
      )}

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
