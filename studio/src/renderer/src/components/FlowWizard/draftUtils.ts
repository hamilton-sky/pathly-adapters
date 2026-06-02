import type { BlockMap, FeedbackRoute, Gate, Transition, TransitionRule } from './types'

export interface WizardDraft {
  version: 1
  flowName: string
  description: string
  step: number
  selectedTemplateId: string | null
  states: string[]
  transitions: Transition[]
  agentMap: Record<string, string>
  gates: Record<string, Gate[]>
  feedbackRoutes: FeedbackRoute[]
  transitionRules: Record<string, TransitionRule>
  storagePath: string
  adapterMap: Record<string, string>
  blockMap: BlockMap
}

export const DRAFT_FILE_NAME = '.flow-wizard-draft.json'

export function serializeDraft(draft: WizardDraft): string {
  return JSON.stringify(draft, null, 2)
}

export function parseDraft(content: string): WizardDraft | null {
  try {
    const parsed = JSON.parse(content) as Partial<WizardDraft>
    if (parsed?.version !== 1) return null
    if (!Array.isArray(parsed.states) || !Array.isArray(parsed.transitions)) return null
    return parsed as WizardDraft
  } catch {
    return null
  }
}

