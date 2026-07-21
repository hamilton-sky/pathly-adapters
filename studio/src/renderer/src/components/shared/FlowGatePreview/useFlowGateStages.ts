import { useEffect, useState } from 'react'
import { useStore } from '../../../store'
import { deriveFlowSteps, type FlowStep } from '../../Monitor/FlowStepsPanel/flowSteps'
import { composeSkillPrompt, type ComposedSegment } from '../../../services/skillCompose'
import { fetchFlowGraph } from './flowGraph'

export interface GateStage {
  skillRef: string
  role: string
  prompt: string
  segments: ComposedSegment[]
}

interface FlowGateStages {
  steps: FlowStep[]
  stageOf: (state: string) => GateStage | undefined
  loading: boolean
}

/**
 * Composes every stage of `flow` up-front — one composeSkillPrompt call per state that
 * carries an agent_map skill ref — so the gate can preview ANY stage instantly on click.
 * Mirrors useDecomposePreview's per-stage compose (GoalsView), generalized to a whole flow's
 * states via the pure deriveFlowSteps (Monitor/FlowStepsPanel). Data hook — data only, no
 * setters (studio rule); DONE and gate/terminal pseudo-states are dropped by deriveFlowSteps
 * itself and by the agent_map-membership filter below.
 */
export function useFlowGateStages(flow: string): FlowGateStages {
  const projectPath = useStore((st) => st.projectPath)
  const [steps, setSteps] = useState<FlowStep[]>([])
  const [stages, setStages] = useState<Record<string, GateStage>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!flow) {
      setSteps([])
      setStages({})
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    void (async () => {
      const graph = await fetchFlowGraph(flow)
      if (cancelled) return
      if (!graph) {
        setSteps([])
        setStages({})
        setLoading(false)
        return
      }

      const derived = deriveFlowSteps(graph.states, graph.roleMap, null, []).filter(
        (s) => !!graph.agentMap[s.state],
      )
      setSteps(derived)

      const entries = await Promise.all(
        derived.map(async (step) => {
          const skillRef = graph.agentMap[step.state]
          const composed = await composeSkillPrompt(skillRef, { projectRoot: projectPath })
          const stage: GateStage = {
            skillRef,
            role: step.role,
            prompt:
              composed?.prompt?.trim() ||
              `# ${step.role || step.state}\n_(the ${skillRef} skill composes at spawn.)_`,
            segments: composed?.segments ?? [],
          }
          return [step.state, stage] as const
        }),
      )
      if (cancelled) return
      setStages(Object.fromEntries(entries))
      setLoading(false)
    })()
    return () => {
      cancelled = true
    }
  }, [flow, projectPath])

  return { steps, stageOf: (state: string) => stages[state], loading }
}
