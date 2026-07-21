import { useEffect, useState } from 'react'
import type { FlowStep } from '../../Monitor/FlowStepsPanel/flowSteps'
import type { GateStage } from './useFlowGateStages'

interface FlowGateState {
  selectedState: string
  /** Effective text per stage: an in-progress edit/Sections-trim when present, else the
   *  stage's composed default — the "default + use-once" pre-fill (DESIGN.md ss5 Q1). */
  text: Record<string, string>
  sectionsUsed: Record<string, boolean>
  selectStage: (state: string) => void
  editText: (state: string, value: string) => void
  applySections: (state: string, value: string) => void
  /** {state: text} for sectionsUsed stages ONLY — mirrors SendPreviewModal's sectionsUsed
   *  gate: a plain submit must leave composition to the server. */
  buildOverrides: () => Record<string, string>
}

/**
 * Per-stage UI state for the gate: which stage is selected, each stage's editable text, and
 * which stages had a Sections cell-config confirmed. UI-state hook (studio rule) — owns
 * state + handlers; stage DATA (the composed defaults) comes from useFlowGateStages via
 * `stageOf`.
 */
export function useFlowGateState(
  steps: FlowStep[],
  stageOf: (state: string) => GateStage | undefined,
): FlowGateState {
  const [selectedState, setSelectedState] = useState('')
  const [edited, setEdited] = useState<Record<string, string>>({})
  const [sectionsUsed, setSectionsUsed] = useState<Record<string, boolean>>({})

  // Default the selection to the first step once steps load; never clobbers a later pick.
  useEffect(() => {
    if (!selectedState && steps.length > 0) setSelectedState(steps[0].state)
  }, [steps, selectedState])

  const text: Record<string, string> = {}
  for (const step of steps) {
    text[step.state] = edited[step.state] ?? stageOf(step.state)?.prompt ?? ''
  }

  function selectStage(state: string): void {
    setSelectedState(state)
  }

  function editText(state: string, value: string): void {
    setEdited((prev) => ({ ...prev, [state]: value }))
  }

  function applySections(state: string, value: string): void {
    setEdited((prev) => ({ ...prev, [state]: value }))
    setSectionsUsed((prev) => ({ ...prev, [state]: true }))
  }

  function buildOverrides(): Record<string, string> {
    const out: Record<string, string> = {}
    for (const state of Object.keys(sectionsUsed)) {
      // Only send an override for a stage that actually COMPOSED (non-empty segments). A
      // fail-soft STUB (compose failed → segments=[]) must never be sent verbatim: it has no
      // skill body and no completion-report fragment, so the stage would spawn blind and the run
      // would vanish/unbilled (no AGENT_DONE). Such a stage falls back to plain-submit → the
      // server composes it normally.
      const composed = (stageOf(state)?.segments?.length ?? 0) > 0
      if (sectionsUsed[state] && text[state] && composed) out[state] = text[state]
    }
    return out
  }

  return { selectedState, text, sectionsUsed, selectStage, editText, applySections, buildOverrides }
}
