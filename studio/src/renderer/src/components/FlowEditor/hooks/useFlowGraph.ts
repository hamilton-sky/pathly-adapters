import { useCallback, useEffect, useRef } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import {
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type NodeMouseHandler,
  type EdgeMouseHandler,
  type Node,
  type Edge
} from 'reactflow'
import type { FlowYaml } from '../../../types'
import type { Theme } from '../../../theme'
import { flowToGraph, type StateNodeData } from '../utils/flowToGraph'

interface UseFlowGraphReturn {
  nodes: ReturnType<typeof useNodesState>[0]
  edges: ReturnType<typeof useEdgesState>[0]
  onNodesChange: ReturnType<typeof useNodesState>[2]
  onEdgesChange: ReturnType<typeof useEdgesState>[2]
  onConnect: (connection: Connection) => void
  onNodeClick: NodeMouseHandler
  onEdgeClick: EdgeMouseHandler
  handleAgentChange: (stateId: string, value: string) => void
  handleAddTransitionRule: (source: string) => void
  handleAddTransitionAction: (source: string, target: string) => void
  dataRef: React.MutableRefObject<FlowYaml>
  setNodes: Dispatch<SetStateAction<Node<StateNodeData>[]>>
  setEdges: Dispatch<SetStateAction<Edge[]>>
}

export function useFlowGraph(
  data: FlowYaml,
  t: Theme,
  onChange: (updated: FlowYaml) => void,
  onNodeClick: (stateId: string) => void,
  onEdgeClick: (edgeId: string, source: string, target: string) => void
): UseFlowGraphReturn {
  const { nodes: initNodes, edges: initEdges } = flowToGraph(data, t)
  const [nodes, setNodes, onNodesChange] = useNodesState(initNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initEdges)

  const dataRef = useRef(data)
  const flowIdRef = useRef(data.flow)
  const stateIdsRef = useRef(new Set(data.states ?? []))

  useEffect(() => {
    dataRef.current = data

    // Full rebuild when the selected flow file changes (different flow identity)
    if (data.flow !== flowIdRef.current) {
      flowIdRef.current = data.flow
      stateIdsRef.current = new Set(data.states ?? [])
      const { nodes: newNodes, edges: newEdges } = flowToGraph(data, t)
      setNodes(newNodes)
      setEdges(newEdges)
      return
    }

    // Sync nodes when states are added or removed (e.g. "+ Add state", drag-drop)
    const prevIds = stateIdsRef.current
    const nextIds = new Set(data.states ?? [])
    const hasStateChange =
      [...nextIds].some((id) => !prevIds.has(id)) ||
      [...prevIds].some((id) => !nextIds.has(id))

    stateIdsRef.current = nextIds

    if (hasStateChange) {
      setNodes((currentNodes) => {
        const posMap = new Map(currentNodes.map((n) => [n.id, n.position]))
        const maxX = currentNodes.length > 0 ? Math.max(...currentNodes.map((n) => n.position.x)) : -220
        const transitionEntries = Object.entries(data.transitions ?? {})
        return (data.states ?? []).map((state) => {
          const pos = posMap.get(state) ?? { x: maxX + 220, y: 100 }
          const outgoingStates = data.transitions[state] ?? []
          const incomingStates = transitionEntries
            .filter(([, targets]) => targets.includes(state))
            .map(([src]) => src)
          return {
            id: state,
            type: 'stateNode' as const,
            position: pos,
            data: { state, agent: data.agent_map[state] ?? '', outgoingStates, incomingStates },
          }
        })
      })
    }

    // Always sync edges (handles transition changes without state set changes)
    const { edges: newEdges } = flowToGraph(data, t)
    setEdges(newEdges)
  }, [data, t, setNodes, setEdges])

  const handleConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge(connection, eds))
      const { source, target } = connection
      if (!source || !target) return
      const d = dataRef.current
      const existing = d.transitions[source] ?? []
      if (!existing.includes(target)) {
        const updated: FlowYaml = {
          ...d,
          transitions: { ...d.transitions, [source]: [...existing, target] }
        }
        onChange(updated)
      }
    },
    [setEdges, onChange]
  )

  const handleNodeClick: NodeMouseHandler = useCallback((_evt, node) => {
    onNodeClick(node.id)
  }, [onNodeClick])

  const handleEdgeClick: EdgeMouseHandler = useCallback((_evt, edge) => {
    onEdgeClick(edge.id, edge.source, edge.target)
  }, [onEdgeClick])

  function handleAgentChange(stateId: string, value: string): void {
    const d = dataRef.current
    const updated: FlowYaml = {
      ...d,
      agent_map: { ...d.agent_map, [stateId]: value }
    }
    onChange(updated)
  }

  function handleAddTransitionRule(source: string): void {
    const d = dataRef.current
    const rules = (d.transition_rules as Record<string, Record<string, unknown>> | undefined) ?? {}
    const existing = (rules[source] as Record<string, unknown> | undefined) ?? {}
    const updated: FlowYaml = {
      ...d,
      transition_rules: { ...rules, [source]: { ...existing, default: '' } }
    }
    onChange(updated)
  }

  function handleAddTransitionAction(source: string, target: string): void {
    const d = dataRef.current
    const actions = (d.transition_actions as Record<string, unknown[]> | undefined) ?? {}
    const key = `${source}->${target}`
    const existing = (actions[key] as unknown[] | undefined) ?? []
    const updated: FlowYaml = {
      ...d,
      transition_actions: { ...actions, [key]: [...existing, { skill: '', message: '' }] }
    }
    onChange(updated)
  }

  return {
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onConnect: handleConnect,
    onNodeClick: handleNodeClick,
    onEdgeClick: handleEdgeClick,
    handleAgentChange,
    handleAddTransitionRule,
    handleAddTransitionAction,
    dataRef,
    setNodes,
    setEdges
  }
}
