import { useRef } from 'react'
import type { Edge, Connection } from 'reactflow'
import { updateEdge } from 'reactflow'
import type { Dispatch, SetStateAction } from 'react'
import type { FlowYaml } from '../../../../types'

interface UseEdgeReconnectArgs {
  dataRef: React.MutableRefObject<FlowYaml>
  onChange: (updated: FlowYaml) => void
  setEdges: Dispatch<SetStateAction<Edge[]>>
}

export function useEdgeReconnect({ dataRef, onChange, setEdges }: UseEdgeReconnectArgs) {
  const edgeUpdateSuccessful = useRef(true)

  function handleEdgeUpdateStart(): void {
    edgeUpdateSuccessful.current = false
  }

  function handleEdgeUpdate(oldEdge: Edge, newConnection: Connection): void {
    edgeUpdateSuccessful.current = true
    setEdges((eds) => updateEdge(oldEdge, newConnection, eds))

    const d = dataRef.current
    const oldSource = oldEdge.source
    const oldTarget = oldEdge.target
    const newSource = newConnection.source ?? oldSource
    const newTarget = newConnection.target ?? oldTarget

    if (oldSource === newSource && oldTarget === newTarget) return

    const newTransitions = { ...d.transitions }
    if (newTransitions[oldSource]) {
      newTransitions[oldSource] = newTransitions[oldSource].filter((t) => t !== oldTarget)
      if (newTransitions[oldSource].length === 0) delete newTransitions[oldSource]
    }
    if (!newTransitions[newSource]) newTransitions[newSource] = []
    if (!newTransitions[newSource].includes(newTarget)) {
      newTransitions[newSource] = [...newTransitions[newSource], newTarget]
    }
    onChange({ ...d, transitions: newTransitions })
  }

  function handleEdgeUpdateEnd(_: MouseEvent | TouchEvent, edge: Edge): void {
    if (!edgeUpdateSuccessful.current) {
      const d = dataRef.current
      const newTransitions = { ...d.transitions }
      if (newTransitions[edge.source]) {
        newTransitions[edge.source] = newTransitions[edge.source].filter((t) => t !== edge.target)
        if (newTransitions[edge.source].length === 0) delete newTransitions[edge.source]
      }
      onChange({ ...d, transitions: newTransitions })
      setEdges((eds) => eds.filter((e) => e.id !== edge.id))
    }
    edgeUpdateSuccessful.current = true
  }

  return { handleEdgeUpdateStart, handleEdgeUpdate, handleEdgeUpdateEnd }
}
