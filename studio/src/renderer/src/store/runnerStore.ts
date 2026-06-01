import { create } from 'zustand'

export type RunnerStatus = 'idle' | 'running' | 'paused' | 'blocked' | 'error' | 'done'
export type SessionKind = 'opened' | 'continued' | 'degraded'

export interface DecisionMenuItem {
  id: string
  label: string
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
  setRunnerState: (patch: Partial<Omit<RunnerState, 'setRunnerState' | 'resetRunner' | 'setDecisionMenu' | 'setRunnerConfig'>>) => void
  resetRunner: () => void
  setDecisionMenu: (items: DecisionMenuItem[] | null) => void
  setRunnerConfig: (topic: string, projectRoot: string) => void
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
}

export const useRunnerStore = create<RunnerState>()((set) => ({
  ...initialState,
  setRunnerState: (patch) => set((s) => ({ ...s, ...patch })),
  resetRunner: () => set((s) => ({ ...s, ...initialState })),
  setDecisionMenu: (items) => set((s) => ({ ...s, decisionMenu: items })),
  setRunnerConfig: (topic, projectRoot) => set((s) => ({ ...s, topic, projectRoot })),
}))
