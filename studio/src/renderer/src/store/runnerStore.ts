import { create } from 'zustand'
import { useTerminalStore } from './terminalStore'

export type RunnerStatus = 'idle' | 'running' | 'paused' | 'blocked' | 'error' | 'done' | 'aborted'
export type SessionKind = 'opened' | 'continued' | 'degraded'

export interface DecisionMenuItem {
  id: string
  label: string
}

export interface StageLogEntry {
  stage: string
  adapter: string | null
  tabId: string | null
  mode: 'terminal' | 'headless' | null
  startedAt: number
  endedAt: number | null
  exitCode: number | null
}

export interface HistoricalRun {
  stageLog: StageLogEntry[]
  runStartedAt: number | null
  cost: number
}

interface RunnerState {
  status: RunnerStatus
  stage: string | null
  adapter: string | null
  cost: number
  sessionKind: SessionKind | null
  decisionMenu: DecisionMenuItem[] | null
  errorMessage: string | null
  topic: string | null
  projectRoot: string | null
  stageLog: StageLogEntry[]
  activeRunnerTabId: string | null
  logCardExpanded: boolean
  runStartedAt: number | null
  runHistory: HistoricalRun[]
  setRunnerState: (patch: Partial<Omit<RunnerState, 'setRunnerState' | 'resetRunner' | 'setDecisionMenu' | 'setRunnerConfig' | 'recordStageStart' | 'recordStageEnd' | 'attachTerminalToStage' | 'setActiveRunnerTabId' | 'setLogCardExpanded' | 'jumpToLiveTab' | 'snapshotRun' | 'resetRunHistory'>>) => void
  resetRunner: () => void
  setDecisionMenu: (items: DecisionMenuItem[] | null) => void
  setRunnerConfig: (topic: string, projectRoot: string) => void
  recordStageStart: (stage: string, adapter: string | null, tabId: string | null) => void
  recordStageEnd: (exitCode: number) => void
  attachTerminalToStage: (tabId: string | null, mode: 'terminal' | 'headless') => void
  setActiveRunnerTabId: (tabId: string | null) => void
  setLogCardExpanded: (expanded: boolean) => void
  jumpToLiveTab: () => void
  snapshotRun: () => void
  resetRunHistory: () => void
}

const initialState = {
  status: 'idle' as RunnerStatus,
  stage: null,
  adapter: null,
  cost: 0,
  sessionKind: null,
  decisionMenu: null,
  errorMessage: null,
  topic: null,
  projectRoot: null,
  stageLog: [] as StageLogEntry[],
  activeRunnerTabId: null,
  logCardExpanded: false,
  runStartedAt: null,
  runHistory: [] as HistoricalRun[],
}

export const useRunnerStore = create<RunnerState>()((set, get) => ({
  ...initialState,
  setRunnerState: (patch) => set((s) => ({ ...s, ...patch })),
  resetRunner: () => set((s) => ({ ...s, ...initialState })),
  setDecisionMenu: (items) => set((s) => ({ ...s, decisionMenu: items })),
  setRunnerConfig: (topic, projectRoot) => set((s) => ({ ...s, topic, projectRoot })),
  recordStageStart: (stage, adapter, tabId) => set((s) => ({
    ...s,
    activeRunnerTabId: tabId,
    runStartedAt: s.stageLog.length === 0 ? Date.now() : s.runStartedAt,
    stageLog: [...s.stageLog, { stage, adapter, tabId, mode: null, startedAt: Date.now(), endedAt: null, exitCode: null }],
  })),
  attachTerminalToStage: (tabId, mode) => set((s) => {
    if (s.stageLog.length === 0) return s
    const updated = [...s.stageLog]
    updated[updated.length - 1] = { ...updated[updated.length - 1], tabId, mode }
    return { ...s, activeRunnerTabId: tabId, stageLog: updated }
  }),
  recordStageEnd: (exitCode) => set((s) => {
    if (s.stageLog.length === 0) return s
    const updated = [...s.stageLog]
    updated[updated.length - 1] = { ...updated[updated.length - 1], endedAt: Date.now(), exitCode }
    return { ...s, stageLog: updated }
  }),
  setActiveRunnerTabId: (tabId) => set((s) => ({ ...s, activeRunnerTabId: tabId })),
  setLogCardExpanded: (expanded) => set((s) => ({ ...s, logCardExpanded: expanded })),
  jumpToLiveTab: () => {
    const { activeRunnerTabId } = get()
    if (!activeRunnerTabId) return
    const ts = useTerminalStore.getState()
    if (!ts.open) ts.toggle()
    ts.openTab(activeRunnerTabId)
  },
  snapshotRun: () => {
    if (get().stageLog.length === 0) return
    set((s) => ({
      runHistory: [...s.runHistory, { stageLog: s.stageLog, runStartedAt: s.runStartedAt, cost: s.cost }],
      stageLog: [],
      runStartedAt: null,
      activeRunnerTabId: null,
    }))
  },
  resetRunHistory: () => set({ runHistory: [] }),
}))
