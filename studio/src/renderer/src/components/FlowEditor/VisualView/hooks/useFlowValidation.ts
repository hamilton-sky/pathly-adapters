import { useMemo } from 'react'
import type { Node, Edge } from 'reactflow'
import type { FlowYaml } from '../../../../types'
import type { Theme } from '../../../../theme'
import { validateFlow } from '../../utils/validateFlow'
import type { FlowValidationIssue } from '../../utils/validateFlow'

interface UseFlowValidationArgs {
  data: FlowYaml
  knownBehaviors: string[]
  nodes: Node[]
  edges: Edge[]
  t: Theme
}

interface UseFlowValidationResult {
  validationIssues: FlowValidationIssue[]
  nodesWithIssues: Node[]
  edgesWithValidation: Edge[]
  hasErrors: boolean
  hasWarnings: boolean
}

export function useFlowValidation({ data, knownBehaviors, nodes, edges, t }: UseFlowValidationArgs): UseFlowValidationResult {
  const validationIssues = useMemo(
    () => validateFlow(data, knownBehaviors),
    [data, knownBehaviors]
  )

  const nodesWithIssues = useMemo(
    () =>
      nodes.map((node): Node => {
        const nodeIssues = validationIssues.filter((i) => i.target === 'node' && i.id === node.id)
        const baseData = node.data as Record<string, unknown>
        const isStart = data.states[0] === node.id
        return {
          ...node,
          data: { ...baseData, issues: nodeIssues.length > 0 ? nodeIssues : undefined, isStart },
        }
      }),
    [nodes, validationIssues, data.states]
  )

  const edgesWithValidation = useMemo(
    () =>
      edges.map((edge) => {
        const edgeKey = `${edge.source}->${edge.target}`
        const edgeIssues = validationIssues.filter((i) => i.target === 'edge' && i.id === edgeKey)
        if (edgeIssues.length === 0) return edge
        const hasError = edgeIssues.some((i) => i.level === 'error')
        return { ...edge, style: { ...edge.style, stroke: hasError ? t.red : t.yellow } }
      }),
    [edges, validationIssues, t]
  )

  const hasErrors = validationIssues.some((i) => i.level === 'error')
  const hasWarnings = validationIssues.some((i) => i.level === 'warning')

  return {
    validationIssues,
    nodesWithIssues,
    edgesWithValidation,
    hasErrors,
    hasWarnings,
  }
}


