import { vi, describe, it, expect, beforeEach } from 'vitest'

// Mock the two leaf services so we can assert exactly how aiRouter dispatches.
vi.mock('./modelManager', () => ({
  runModel: vi.fn().mockResolvedValue({ text: 'model-result', cost_usd: 0.01 }),
}))
vi.mock('./cliEngine', async () => {
  const actual = await vi.importActual<typeof import('./cliEngine')>('./cliEngine')
  return { ...actual, buildHeadlessArgv: vi.fn(actual.buildHeadlessArgv) }
})
// projectStore supplies the default cwd; pin it so the engine spawn is deterministic.
vi.mock('../store/projectStore', () => ({
  useProjectStore: { getState: () => ({ projectPath: 'C:/proj' }) },
}))
// terminalStore — aiRouter registers a tab (addTab/updateTabStatus/closeTab) so the
// engine run is visible in the CLI bar. Mock getState() to capture those calls.
const addTab = vi.fn()
const updateTabStatus = vi.fn()
const openTab = vi.fn()
const closeTab = vi.fn()
vi.mock('../store/terminalStore', () => ({
  useTerminalStore: { getState: () => ({ addTab, updateTabStatus, openTab, closeTab }) },
}))

import * as modelManager from './modelManager'
import * as cliEngine from './cliEngine'
import { runJob, isOff, AI_SELECTION_OFF } from './aiRouter'

const runModelMock = modelManager.runModel as ReturnType<typeof vi.fn>
const buildArgvMock = cliEngine.buildHeadlessArgv as ReturnType<typeof vi.fn>

// terminal mock — onExit registers a listener we fire manually; spawn records its args.
let exitCb: ((tabId: string, exitCode?: number, tail?: string) => void) | null = null
const spawn = vi.fn().mockResolvedValue(undefined)
const onExit = vi.fn((cb: (tabId: string, exitCode?: number, tail?: string) => void) => {
  exitCb = cb
  return () => { exitCb = null }
})

beforeEach(() => {
  vi.clearAllMocks()
  exitCb = null
  ;(window as unknown as { pathly: { terminal: unknown } }).pathly = {
    ...(window as unknown as { pathly: object }).pathly,
    terminal: { spawn, onExit },
  }
})

describe('aiRouter.runJob', () => {
  it('model selection dispatches to modelManager.runModel', async () => {
    const result = await runJob(
      { kind: 'summarize', prompt: 'hello' },
      { type: 'model', id: 'phi-4-mini' },
    )
    expect(runModelMock).toHaveBeenCalledWith('phi-4-mini', 'hello')
    expect(spawn).not.toHaveBeenCalled()
    expect(result).toEqual({ text: 'model-result', cost_usd: 0.01 })
  })

  it('engine selection builds argv via buildHeadlessArgv and spawns a headless PTY', async () => {
    const p = runJob(
      { kind: 'summarize', prompt: 'summarize this' },
      { type: 'engine', id: 'claude' },
    )
    // onExit must be subscribed before spawn (lifecycle invariant).
    expect(onExit).toHaveBeenCalledTimes(1)
    expect(buildArgvMock).toHaveBeenCalledWith('claude', 'summarize this', { jsonResult: true })
    expect(spawn).toHaveBeenCalledTimes(1)
    const [tabId, cwd, command, argv] = spawn.mock.calls[0]
    expect(typeof tabId).toBe('string')
    expect(cwd).toBe('C:/proj') // default cwd from projectStore
    expect(command).toBeUndefined()
    expect(argv[0]).toBe('claude')
    expect(runModelMock).not.toHaveBeenCalled()

    // The run registers a terminal tab and is marked running before exit (visible in the bar).
    expect(addTab).toHaveBeenCalledTimes(1)
    expect(addTab.mock.calls[0][0]).toBe(tabId)
    expect(addTab.mock.calls[0][3]).toBe('claude') // kind = adapter
    expect(updateTabStatus).toHaveBeenCalledWith(tabId, 'running')

    // Resolve only when OUR tabId exits 0; tail becomes the result text.
    exitCb?.('some-other-tab', 0, 'ignored')
    exitCb?.(tabId, 0, 'engine summary text')
    await expect(p).resolves.toEqual({ text: 'engine summary text' })
    // On success the tab is marked done and closed.
    expect(updateTabStatus).toHaveBeenCalledWith(tabId, 'done')
    expect(closeTab).toHaveBeenCalledWith(tabId)
  })

  it('engine selection honours an explicit job.cwd', async () => {
    const p = runJob(
      { kind: 'summarize', prompt: 'x', cwd: 'D:/elsewhere' },
      { type: 'engine', id: 'codex' },
    )
    const [, cwd] = spawn.mock.calls[0]
    expect(cwd).toBe('D:/elsewhere')
    exitCb?.(spawn.mock.calls[0][0], 0, 'ok')
    await expect(p).resolves.toEqual({ text: 'ok' })
  })

  it('engine selection rejects on a non-zero exit with the tail', async () => {
    const p = runJob({ kind: 'generic', prompt: 'x' }, { type: 'engine', id: 'claude' })
    const tabId = spawn.mock.calls[0][0]
    exitCb?.(tabId, 1, 'boom')
    await expect(p).rejects.toThrow('boom')
    // A failed run marks the tab error and closes it.
    expect(updateTabStatus).toHaveBeenCalledWith(tabId, 'error')
    expect(closeTab).toHaveBeenCalledWith(tabId)
  })

  it('the Off sentinel is recognised and rejected by runJob', async () => {
    expect(isOff(AI_SELECTION_OFF)).toBe(true)
    expect(isOff({ type: 'model', id: 'phi-4-mini' })).toBe(false)
    await expect(
      runJob({ kind: 'summarize', prompt: 'x' }, AI_SELECTION_OFF),
    ).rejects.toThrow(/Off/)
  })
})
