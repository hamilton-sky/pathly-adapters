import type { Node, Edge } from 'reactflow'
import { MarkerType } from 'reactflow'
import type { Theme } from '../../../theme'
import type { FlowYaml } from '../../../types'
import type { FlowValidationIssue } from './validateFlow'

export interface StateNodeData {
  state: string
  agent: string
  isStart?: boolean
  issues?: FlowValidationIssue[]
  outgoingStates?: string[]
  incomingStates?: string[]
  feedbackArrivals?: string[]  // artifacts from feedback_routing that route TO this state
}

interface StateRule {
  default?: string
  on_artifact?: Record<string, string>
  on_content?: Array<{ file?: string; contains?: string; regex?: string; next: string }>
  decide?: { question?: string; options?: Record<string, string>; default?: string }
}

// Failure artifact names get a red edge so they visually stand out
const FAILURE_ARTIFACTS = new Set([
  'REVIEW_FAILURES.md',
  'TEST_FAILURES.md',
  'SCOPE_VIOLATION.md',
  'HUMAN_QUESTIONS.md',
  'BLOCKED_ON_HUMAN.md',
  'MORE_CONVS_NEEDED.md',
])

// Shorten artifact names so self-loop labels fit inside the diagram
const ARTIFACT_ABBREV: Record<string, string> = {
  IMPLEMENTATION_PLAN: 'IMPL_PLAN',
}
function abbreviateArtifact(name: string): string {
  const stem = name.replace(/\.md$/i, '')
  return (ARTIFACT_ABBREV[stem] ?? stem)
}

// For a self-loop, show what artifact the state is WAITING for (the one that advances it out)
function extractSelfLoopLabel(
  rules: Record<string, unknown> | undefined,
  source: string
): string {
  if (!rules) return 'retry'
  const sourceRule = rules[source] as StateRule | undefined
  if (!sourceRule?.on_artifact) return 'retry'
  const advancing = Object.entries(sourceRule.on_artifact)
    .filter(([, tgt]) => tgt !== source)
    .map(([artifact]) => abbreviateArtifact(artifact))
  return advancing.length > 0 ? 'no ' + advancing.join(' / ') : 'retry'
}

// Collect ALL artifacts that route from source→target (not just the first match)
function extractEdgeLabel(
  rules: Record<string, unknown> | undefined,
  source: string,
  target: string
): string {
  if (!rules) return ''

  const sourceRule = rules[source] as StateRule | undefined
  if (!sourceRule) return ''

  if (sourceRule.default === target) return ''

  if (sourceRule.on_artifact) {
    const matches: string[] = []
    for (const [artifact, tgt] of Object.entries(sourceRule.on_artifact)) {
      if (tgt === target) matches.push(artifact)
    }
    if (matches.length > 0) return matches.join(' / ')
  }

  if (sourceRule.on_content) {
    for (const entry of sourceRule.on_content) {
      if (entry.next === target) {
        return entry.contains ?? entry.regex ?? entry.file ?? 'on content'
      }
    }
  }

  if (sourceRule.decide?.options) {
    for (const [option, tgt] of Object.entries(sourceRule.decide.options)) {
      if (tgt === target) return option
    }
  }

  return ''
}

// Amber for backward loops, red for failure artifact routes, blue for normal forward
const FORWARD_COLOR = '#3B82F6'   // blue
const BACKWARD_COLOR = '#F59E0B'  // amber
const FAILURE_COLOR = '#EF4444'   // red
const FEEDBACK_COLOR = '#8B5CF6'  // purple — feedback_routing escalations

export function flowToGraph(data: FlowYaml, t: Theme): { nodes: Node<StateNodeData>[]; edges: Edge[] } {
  const states = data.states ?? []
  const stateSet = new Set(states)

  // Build index map for direction detection
  const stateIndex = new Map<string, number>()
  states.forEach((s, i) => stateIndex.set(s, i))

  const transitionEntries = Object.entries(data.transitions ?? {})

  // Build feedback_routing arrivals per state.
  // Uses role_map (semantic roles) when available; falls back to agent_map for flows
  // that already use short agent names (e.g. debug.flow where agent_map has 'builder').
  const feedbackArrivalsMap = new Map<string, string[]>()
  if (data.feedback_routing) {
    const roleSource: Record<string, string> = data.role_map ?? data.agent_map ?? {}
    const roleToStates = new Map<string, string[]>()
    for (const [state, role] of Object.entries(roleSource)) {
      const existing = roleToStates.get(role) ?? []
      roleToStates.set(role, [...existing, state])
    }
    for (const [artifactTag, roleName] of Object.entries(data.feedback_routing)) {
      const targetStates = roleToStates.get(roleName as string) ?? []
      for (const targetState of targetStates) {
        const existing = feedbackArrivalsMap.get(targetState) ?? []
        feedbackArrivalsMap.set(targetState, [...existing, artifactTag + '.md'])
      }
    }
  }

  const nodes: Node<StateNodeData>[] = states.map((state, i) => {
    const outgoingStates = data.transitions[state] ?? []
    const incomingStates = transitionEntries
      .filter(([, targets]) => targets.includes(state))
      .map(([src]) => src)
    return {
      id: state,
      type: 'stateNode',
      // Initial positions: vertical stack for TB layout (overridden by Auto-layout)
      position: { x: 200, y: i * 140 },
      data: {
        state,
        agent: data.agent_map?.[state] ?? '',
        outgoingStates,
        incomingStates,
        feedbackArrivals: feedbackArrivalsMap.get(state),
      }
    }
  })

  const edges: Edge[] = []
  const rules = data.transition_rules as Record<string, unknown> | undefined

  // Global counter — alternates ALL backward edges left/right so no two share the same side path
  let backwardIdx = 0

  for (const [source, targets] of Object.entries(data.transitions ?? {})) {
    if (!stateSet.has(source)) continue

    for (const target of targets) {
      if (!stateSet.has(target)) continue

      const edgeId = `${source}__${target}`
      const label = extractEdgeLabel(rules, source, target)

      const srcIdx = stateIndex.get(source) ?? 0
      const tgtIdx = stateIndex.get(target) ?? 0
      const isBackward = srcIdx > tgtIdx || source === target
      const isSelfLoop = source === target
      const isFailure = isBackward && label.split(' / ').some(l => FAILURE_ARTIFACTS.has(l))

      const edgeColor = isFailure ? FAILURE_COLOR : isBackward ? BACKWARD_COLOR : FORWARD_COLOR

      let edgeType: string
      let sourceHandle: string | undefined
      let targetHandle: string | undefined

      if (isSelfLoop) {
        // Self-loop: use right side handles only, labeled with condition
        edgeType = 'smoothstep'
        sourceHandle = 'right-src'
        targetHandle = 'right-tgt'
        backwardIdx++
      } else if (isBackward) {
        // Alternate globally: even index → right side, odd → left side
        const useRight = backwardIdx % 2 === 0
        backwardIdx++
        edgeType = 'smoothstep'
        sourceHandle = useRight ? 'right-src' : 'left-src'
        targetHandle = useRight ? 'right-tgt' : 'left-tgt'
      } else {
        edgeType = 'smoothstep'
        sourceHandle = 'bot-src'    // exits bottom center
        targetHandle = 'top-tgt'    // enters top center — clean vertical line
      }

      const selfLoopLabel = isSelfLoop ? extractSelfLoopLabel(rules, source) : label

      edges.push({
        id: edgeId,
        source,
        target,
        sourceHandle,
        targetHandle,
        type: edgeType,
        animated: false,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: edgeColor,
          width: 14,
          height: 14,
        },
        ...(selfLoopLabel ? {
          label: selfLoopLabel,
          labelStyle: {
            fill: isFailure ? FAILURE_COLOR : isBackward ? BACKWARD_COLOR : t.textSecondary,
            fontSize: '10px',
            fontWeight: isBackward ? 500 : 400,
          },
          labelBgStyle: { fill: t.bgMantle, fillOpacity: 0.9 },
          labelBgPadding: [4, 2] as [number, number],
          labelBgBorderRadius: 3,
        } : {}),
        style: {
          stroke: edgeColor,
          strokeWidth: 1.5,
          ...(isSelfLoop ? { strokeDasharray: '4 2' } : {}),
        },
      })
    }
  }

  return { nodes, edges }
}
