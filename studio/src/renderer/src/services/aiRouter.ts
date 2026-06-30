// aiRouter — the single dispatch point that turns an AiSelection (a model or a
// CLI engine) plus an AiJob into an AiResult. It is the layer above the two leaf
// services: modelManager (local models / Brightsky) and cliEngine (headless CLI
// argv). UI consumers (HQ, ArtifactsView) call runJob and never touch the
// transports directly.
//
// Plain service module — no React. Engine dispatch reuses the exact PTY one-shot
// mechanism proven in MarkdownEditor/.../useEditorAgentActions.ts: subscribe to
// terminal.onExit BEFORE spawning, only react to our own tabId, unsubscribe once.

import { runModel } from './modelManager'
import { buildHeadlessArgv, type CliAdapter } from './cliEngine'
import { useProjectStore } from '../store/projectStore'
import { useTerminalStore, type TerminalTab } from '../store/terminalStore'

export type AiSelection = { type: 'model' | 'engine'; id: string }
export interface AiJob {
  kind: 'summarize' | 'generic'
  prompt: string
  cwd?: string
}
export interface AiResult {
  text: string
  cost_usd?: number
}

/**
 * Sentinel meaning "no AI target". AiTargetSelector emits this when allowOff is
 * on and the user picks "Off". runJob does NOT accept it — consumers must check
 * for it and skip the run. Exported so consumers compare against one value.
 */
export const AI_SELECTION_OFF: AiSelection = { type: 'model', id: '__off__' }
export const isOff = (sel: AiSelection | null): boolean =>
  sel != null && sel.type === AI_SELECTION_OFF.type && sel.id === AI_SELECTION_OFF.id

/** Project root used as the spawn cwd when the job doesn't pin its own. */
function defaultCwd(): string {
  return useProjectStore.getState().projectPath || '.'
}

/**
 * Spawn a CLI engine headless one-shot and resolve with its stdout tail.
 * Returns both the promise and an abort function.
 *
 * The run opens a real terminal tab (addTab + updateTabStatus 'running' + openTab) so
 * it is visible in the CLI tab list / monitor bar exactly like every other CLI-engine
 * spawn. On natural exit (or a spawn throw) the tab status is set 'done'/'error' and the
 * tab is closed.
 *
 * abort() does NOT just call terminal.kill and wait for onExit: on Windows the PTY is
 * force-killed via `taskkill /F`, which does NOT fire node-pty's onExit, so the renderer
 * would never receive terminal:exit and the monitor would show the run as ACTIVE forever.
 * Instead abort settles the promise and closes the tab itself (so the monitor clears
 * immediately), then kills the PTY. The onExit listener is unsubscribed + guarded by
 * `settled`, so a late real exit is ignored.
 */
function runEngineCancellable(
  adapter: CliAdapter,
  prompt: string,
  cwd: string,
): { promise: Promise<AiResult>; abort: () => void } {
  const argv = buildHeadlessArgv(adapter, prompt, { streamJson: true })
  const tabId = `airouter-${adapter}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
  const term = useTerminalStore.getState()
  term.addTab(tabId, `Summary · ${adapter}`, 'left', adapter as TerminalTab['kind'], undefined, undefined, prompt)
  term.updateTabStatus(tabId, 'running')
  term.openTab(tabId)   // reveal it like every other CLI-engine spawn

  let settled = false
  let unsubscribe = (): void => {}
  let rejectPromise: (e: Error) => void = () => {}
  const finish = (status: 'done' | 'error'): void => {
    const t = useTerminalStore.getState()
    t.updateTabStatus(tabId, status)
    t.closeTab(tabId)
  }

  const promise = new Promise<AiResult>((resolve, reject) => {
    rejectPromise = reject
    unsubscribe = window.pathly.terminal.onExit(
      (exitedTabId: string, exitCode?: number, tail?: string) => {
        if (exitedTabId !== tabId || settled) return
        settled = true
        unsubscribe()
        if (exitCode && exitCode !== 0) {
          finish('error')
          reject(new Error(tail?.trim() || `${adapter} exited with code ${exitCode}`))
        } else {
          finish('done')
          resolve({ text: tail ?? '' })
        }
      },
    )
    window.pathly.terminal.spawn(tabId, cwd, undefined, argv, undefined, {
      telemetry: { scopeTier: 'project', label: 'ai-summary', role: 'ai-router' },
    }).catch((e: unknown) => {
      if (settled) return
      settled = true
      unsubscribe()
      finish('error')
      reject(e instanceof Error ? e : new Error(String(e)))
    })
  })

  const abort = (): void => {
    if (settled) return
    settled = true
    unsubscribe()
    finish('error')                          // closes the tab → monitor clears at once
    void window.pathly.terminal.kill(tabId)  // kill the PTY (main also frees the scheduler slot)
    rejectPromise(new Error('aborted'))       // useResummarize treats 'aborted' as a clean stop
  }

  return { promise, abort }
}

function runEngine(adapter: CliAdapter, prompt: string, cwd: string): Promise<AiResult> {
  return runEngineCancellable(adapter, prompt, cwd).promise
}

/** Dispatch a job to either a local model or a CLI engine, per the selection. */
export async function runJob(job: AiJob, selection: AiSelection): Promise<AiResult> {
  if (isOff(selection)) {
    throw new Error('aiRouter.runJob called with the Off sentinel; consumers must skip Off')
  }
  if (selection.type === 'model') {
    return runModel(selection.id, job.prompt)
  }
  return runEngine(selection.id as CliAdapter, job.prompt, job.cwd ?? defaultCwd())
}

/**
 * Like runJob but returns an abort function alongside the promise. For CLI-engine
 * targets abort kills the PTY immediately; for model targets it marks the result as
 * discarded (the promise rejects with 'aborted'). Callers must check isOff first.
 */
export function runJobWithAbort(
  job: AiJob,
  selection: AiSelection,
): { promise: Promise<AiResult>; abort: () => void } {
  if (isOff(selection)) {
    throw new Error('runJobWithAbort called with the Off sentinel; consumers must skip Off')
  }
  if (selection.type === 'model') {
    let aborted = false
    const promise = runModel(selection.id, job.prompt).then((r) => {
      if (aborted) throw new Error('aborted')
      return r
    })
    return { promise, abort: () => { aborted = true } }
  }
  return runEngineCancellable(selection.id as CliAdapter, job.prompt, job.cwd ?? defaultCwd())
}
