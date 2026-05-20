import { useCallback } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import type { Node, Edge } from 'reactflow'
import type { FlowYaml } from '../../../../types'
import type { StateNodeData } from '../../utils/flowToGraph'
import type { PanelDetail } from '../constants'
import { generateUniqueStateId } from '../utils/generateUniqueStateId'

interface UseFlowMutationsArgs {
  dataRef: React.MutableRefObject<FlowYaml>
  onChange: (updated: FlowYaml) => void
  setNodes: Dispatch<SetStateAction<Node<StateNodeData>[]>>
  setEdges: Dispatch<SetStateAction<Edge[]>>
  setDetail: Dispatch<SetStateAction<PanelDetail>>
  pendingPositionsRef: React.MutableRefObject<Map<string, { x: number; y: number }>>
}

export function useFlowMutations({
  dataRef,
  onChange,
  setNodes,
  setEdges,
  setDetail,
  pendingPositionsRef,
}: UseFlowMutationsArgs) {
  function removeState(stateId: string): void {
    const d = dataRef.current
    const newStates = d.states.filter((s) => s !== stateId)
    const newTransitions: Record<string, string[]> = {}
    for (const [src, targets] of Object.entries(d.transitions ?? {})) {
      if (src === stateId) continue
      const filtered = targets.filter((t) => t !== stateId)
      if (filtered.length > 0) newTransitions[src] = filtered
    }
    const newAgentMap = { ...d.agent_map }
    delete newAgentMap[stateId]
    const newRules = { ...((d.transition_rules as Record<string, unknown> | undefined) ?? {}) }
    delete newRules[stateId]
    const newActions: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(d.transition_actions ?? {})) {
      if (!k.startsWith(`${stateId}->`) && !k.endsWith(`->${stateId}`)) {
        newActions[k] = v
      }
    }
    onChange({
      ...d,
      states: newStates,
      transitions: newTransitions,
      agent_map: newAgentMap,
      transition_rules: Object.keys(newRules).length > 0 ? newRules : undefined,
      transition_actions: Object.keys(newActions).length > 0 ? newActions : undefined,
    })
    setNodes((nds) => nds.filter((n) => n.id !== stateId))
    setEdges((eds) => eds.filter((e) => e.source !== stateId && e.target !== stateId))
  }

  function removeEdge(source: string, target: string): void {
    const d = dataRef.current
    const newTransitions = { ...d.transitions }
    if (newTransitions[source]) {
      newTransitions[source] = newTransitions[source].filter((t) => t !== target)
      if (newTransitions[source].length === 0) delete newTransitions[source]
    }
    const actionKey = `${source}->${target}`
    const newActions = { ...((d.transition_actions as Record<string, unknown>) ?? {}) }
    delete newActions[actionKey]
    onChange({
      ...d,
      transitions: newTransitions,
      transition_actions: Object.keys(newActions).length > 0 ? newActions : undefined,
    })
    setEdges((eds) => eds.filter((e) => !(e.source === source && e.target === target)))
  }

  const handleRenameState = useCallback(
    (oldId: string, newId: string): void => {
      const d = dataRef.current
      const states = d.states.map((s) => (s === oldId ? newId : s))
      const transitions: Record<string, string[]> = {}
      for (const [src, targets] of Object.entries(d.transitions ?? {})) {
        transitions[src === oldId ? newId : src] = targets.map((t) => (t === oldId ? newId : t))
      }
      const agent_map: Record<string, string> = {}
      for (const [k, v] of Object.entries(d.agent_map ?? {})) {
        agent_map[k === oldId ? newId : k] = v
      }
      const transition_rules: Record<string, unknown> = {}
      if (d.transition_rules) {
        for (const [k, v] of Object.entries(d.transition_rules as Record<string, unknown>)) {
          transition_rules[k === oldId ? newId : k] = v
        }
      }
      const transition_actions: Record<string, unknown> = {}
      if (d.transition_actions) {
        for (const [k, v] of Object.entries(d.transition_actions as Record<string, unknown>)) {
          const newKey = k
            .split('->')
            .map((part) => (part === oldId ? newId : part))
            .join('->')
          transition_actions[newKey] = v
        }
      }
      onChange({
        ...d,
        states,
        transitions,
        agent_map,
        ...(d.transition_rules ? { transition_rules } : {}),
        ...(d.transition_actions ? { transition_actions } : {}),
      })
      setNodes((nds) =>
        nds.map((n): Node<StateNodeData> =>
          n.id !== oldId
            ? n
            : { ...n, id: newId, data: { ...n.data, state: newId } }
        )
      )
      setEdges((eds) =>
        eds.map((e) => ({
          ...e,
          ...(e.source === oldId ? { source: newId } : {}),
          ...(e.target === oldId ? { target: newId } : {}),
          id: `${e.source === oldId ? newId : e.source}__${e.target === oldId ? newId : e.target}`,
        }))
      )
      setDetail({ type: 'node', stateId: newId })
    },
    [dataRef, onChange, setNodes, setEdges, setDetail]
  )

  function handleNodesDelete(deletedNodes: Node[]): void {
    const d = dataRef.current
    const deletedIds = new Set(deletedNodes.map((n) => n.id))

    const states = d.states.filter((s) => !deletedIds.has(s))

    const transitions: Record<string, string[]> = {}
    for (const [src, targets] of Object.entries(d.transitions)) {
      if (deletedIds.has(src)) continue
      const filtered = targets.filter((t) => !deletedIds.has(t))
      transitions[src] = filtered
    }

    const agent_map: Record<string, string> = {}
    for (const [k, v] of Object.entries(d.agent_map)) {
      if (!deletedIds.has(k)) agent_map[k] = v
    }

    const transition_rules: Record<string, unknown> = {}
    if (d.transition_rules) {
      for (const [k, v] of Object.entries(d.transition_rules)) {
        if (!deletedIds.has(k)) transition_rules[k] = v
      }
    }

    const transition_actions: Record<string, unknown> = {}
    if (d.transition_actions) {
      for (const [k, v] of Object.entries(d.transition_actions as Record<string, unknown>)) {
        const isRelated = [...deletedIds].some((id) => k.includes(id))
        if (!isRelated) transition_actions[k] = v
      }
    }

    const updated: FlowYaml = {
      ...d,
      states,
      transitions,
      agent_map,
      ...(d.transition_rules ? { transition_rules } : {}),
      ...(d.transition_actions ? { transition_actions } : {}),
    }
    onChange(updated)
  }

  function handleEdgesDelete(deletedEdges: Edge[]): void {
    const d = dataRef.current
    const newTransitions = { ...d.transitions }
    for (const edge of deletedEdges) {
      const { source, target } = edge
      if (newTransitions[source]) {
        newTransitions[source] = newTransitions[source].filter((t) => t !== target)
        if (newTransitions[source].length === 0) delete newTransitions[source]
      }
    }
    onChange({ ...d, transitions: newTransitions })
  }

  function duplicateState(stateId: string, sourcePosition: { x: number; y: number }): void {
    const d = dataRef.current
    const newId = generateUniqueStateId(stateId, d.states)
    // Place duplicate offset slightly below-right of the original.
    pendingPositionsRef.current.set(newId, { x: sourcePosition.x + 120, y: sourcePosition.y + 80 })
    const newAgentMap = { ...d.agent_map }
    if (d.agent_map[stateId]) newAgentMap[newId] = d.agent_map[stateId]
    onChange({
      ...d,
      states: [...d.states, newId],
      agent_map: newAgentMap,
      transitions: { ...d.transitions },
    })
  }

  return {
    removeState,
    removeEdge,
    duplicateState,
    handleRenameState,
    handleNodesDelete,
    handleEdgesDelete,
  }
}
