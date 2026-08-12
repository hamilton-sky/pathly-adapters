import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AutomationStep, AutomationStepStatus } from '../types/automation'

export type {  AutomationStepStatus }

export interface AutomationState {
  steps: AutomationStep[]
  currentStepIndex: number
  mode: 'staged' | 'auto'
  status: 'idle' | 'running' | 'paused' | 'done' | 'error'
  setSteps: (steps: AutomationStep[]) => void
  approveStep: (id: string) => void
  skipStep: (id: string) => void
  setStepError: (id: string, errorMessage: string) => void
  setMode: (mode: 'staged' | 'auto') => void
  setStatus: (status: AutomationState['status']) => void
  advanceToNext: () => void
  reset: () => void
}

type PersistedSlice = { mode: AutomationState['mode'] }

export const useAutomationStore = create<AutomationState>()(
  persist(
    (set) => ({
      steps: [],
      currentStepIndex: 0,
      mode: 'staged',
      status: 'idle',

      setSteps: (steps) =>
        set({ steps: steps.map((s) => ({ ...s, status: 'pending' as AutomationStepStatus })), currentStepIndex: 0, status: 'idle' }),

      approveStep: (id) =>
        set((s) => ({
          steps: s.steps.map((step) =>
            step.id === id ? { ...step, status: 'approved' as AutomationStepStatus } : step
          ),
        })),

      skipStep: (id) =>
        set((s) => ({
          steps: s.steps.map((step) =>
            step.id === id ? { ...step, status: 'skipped' as AutomationStepStatus } : step
          ),
          currentStepIndex: s.currentStepIndex + 1,
        })),

      setStepError: (id, errorMessage) =>
        set((s) => ({
          steps: s.steps.map((step) =>
            step.id === id ? { ...step, status: 'error' as AutomationStepStatus, errorMessage } : step
          ),
        })),

      setMode: (mode) => set({ mode }),

      setStatus: (status) => set({ status }),

      advanceToNext: () =>
        set((s) => {
          const updated = s.steps.map((step, i) =>
            i === s.currentStepIndex ? { ...step, status: 'done' as AutomationStepStatus } : step
          )
          return { steps: updated, currentStepIndex: s.currentStepIndex + 1 }
        }),

      reset: () => set({ steps: [], currentStepIndex: 0, status: 'idle' }),
    }),
    {
      name: 'pathly-automation-mode',
      partialize: (state): PersistedSlice => ({ mode: state.mode }),
    }
  )
)
