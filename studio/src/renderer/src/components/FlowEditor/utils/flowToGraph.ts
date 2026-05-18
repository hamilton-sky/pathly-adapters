import type { Node, Edge } from 'reactflow'
import type { Theme } from '../../../theme'
import type { FlowYaml } from '../../../types'

export interface StateNodeData {
  state: string
  agent: string
}

export function flowToGraph(data: FlowYaml, t: Theme): { nodes: Node<StateNodeData>[]; edges: Edge[] } {
  const nodes: Node<StateNodeData>[] = (data.states ?? []).map((state, i) => ({
    id: state,
    type: 'stateNode',
    position: { x: i * 220, y: 100 },
    data: { state, agent: data.agent_map[state] ?? '' }
  }))

  const edges: Edge[] = []
  let edgeIdx = 0
  for (const [source, targets] of Object.entries(data.transitions ?? {})) {
    for (const target of targets) {
      const edgeId = `e-${edgeIdx++}`
      const rules = data.transition_rules as Record<string, Record<string, string>> | undefined
      let label = 'default'
      if (rules) {
        for (const [artifact, mapping] of Object.entries(rules)) {
          if (Object.entries(mapping).some(([s, tgt]) => s === source && tgt === target)) {
            label = artifact
            break
          }
        }
      }
      edges.push({
        id: edgeId,
        source,
        target,
        label,
        style: { stroke: t.blue },
        labelStyle: { fill: t.textSecondary, fontSize: '11px' },
        labelBgStyle: { fill: t.bgMantle }
      })
    }
  }

  return { nodes, edges }
}
