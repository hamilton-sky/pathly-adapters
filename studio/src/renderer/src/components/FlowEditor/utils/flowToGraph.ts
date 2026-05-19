import type { Node, Edge } from 'reactflow'
import { MarkerType } from 'reactflow'
import type { Theme } from '../../../theme'
import type { FlowYaml } from '../../../types'

import type { FlowValidationIssue } from './validateFlow'

export interface StateNodeData {
  state: string
  agent: string
  issues?: FlowValidationIssue[]
  outgoingStates?: string[]
  incomingStates?: string[]
}

// Nested transition_rules shape used by the real FSM:
// transition_rules[source].default = target
// transition_rules[source].on_artifact[artifactName] = target
// transition_rules[source].on_content[] = { file, contains?, regex?, next: target }
// transition_rules[source].decide = { question, options: { label: target }, default: label }
interface StateRule {
  default?: string
  on_artifact?: Record<string, string>
  on_content?: Array<{ file?: string; contains?: string; regex?: string; next: string }>
  decide?: { question?: string; options?: Record<string, string>; default?: string }
}

function extractEdgeLabel(
  rules: Record<string, unknown> | undefined,
  source: string,
  target: string
): string {
  if (!rules) return 'default'

  const sourceRule = rules[source] as StateRule | undefined
  if (!sourceRule) return 'default'

  if (sourceRule.default === target) return 'default'

  if (sourceRule.on_artifact) {
    for (const [artifact, tgt] of Object.entries(sourceRule.on_artifact)) {
      if (tgt === target) return artifact
    }
  }

  if (sourceRule.on_content) {
    for (const entry of sourceRule.on_content) {
      if (entry.next === target) {
        return entry.contains ?? entry.regex ?? entry.file ?? 'on_content'
      }
    }
  }

  if (sourceRule.decide?.options) {
    for (const [option, tgt] of Object.entries(sourceRule.decide.options)) {
      if (tgt === target) return option
    }
  }

  return 'default'
}

export function flowToGraph(data: FlowYaml, t: Theme): { nodes: Node<StateNodeData>[]; edges: Edge[] } {
  const stateSet = new Set(data.states ?? [])
  const transitionEntries = Object.entries(data.transitions ?? {})

  const nodes: Node<StateNodeData>[] = (data.states ?? []).map((state, i) => {
    const outgoingStates = data.transitions[state] ?? []
    const incomingStates = transitionEntries
      .filter(([, targets]) => targets.includes(state))
      .map(([src]) => src)
    return {
      id: state,
      type: 'stateNode',
      position: { x: i * 220, y: 100 },
      data: { state, agent: data.agent_map[state] ?? '', outgoingStates, incomingStates }
    }
  })

  const edges: Edge[] = []
  const rules = data.transition_rules as Record<string, unknown> | undefined

  for (const [source, targets] of Object.entries(data.transitions ?? {})) {
    // Skip edges whose source state is not in states list
    if (!stateSet.has(source)) continue

    for (const target of targets) {
      // Skip edges whose target state is not in states list
      if (!stateSet.has(target)) continue

      const edgeId = `${source}__${target}`
      const label = extractEdgeLabel(rules, source, target)

      edges.push({
        id: edgeId,
        source,
        target,
        type: 'smoothstep',
        animated: false,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: t.blue,
          width: 16,
          height: 16,
        },
        label,
        style: { stroke: t.blue, strokeWidth: 1.5 },
        labelStyle: { fill: t.textSecondary, fontSize: '11px' },
        labelBgStyle: { fill: t.bgMantle, fillOpacity: 0.85 },
        labelBgPadding: [4, 2] as [number, number],
        labelBgBorderRadius: 3,
      })
    }
  }

  return { nodes, edges }
}
