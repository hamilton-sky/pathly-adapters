import { useReactFlow } from 'reactflow'
import type { FlowYaml, PathlyCanvasDragItem } from '../../../../types'
import { PATHLY_DRAG_MIME } from '../../../../types'
import { generateUniqueStateId } from '../utils/generateUniqueStateId'

// Approximate half-dimensions of a StateNode — used to center it on the drop point.
const NODE_HALF_W = 115
const NODE_HALF_H = 35

interface UseCanvasDnDArgs {
  dataRef: React.MutableRefObject<FlowYaml>
  onChange: (updated: FlowYaml) => void
  pendingPositionsRef: React.MutableRefObject<Map<string, { x: number; y: number }>>
  canvasRef: React.RefObject<HTMLDivElement>
}

export function useCanvasDnD({ dataRef, onChange, pendingPositionsRef, canvasRef }: UseCanvasDnDArgs) {
  const { getViewport } = useReactFlow()

  /** Convert a client (screen) coordinate to a flow-space coordinate. */
  function clientToFlow(clientX: number, clientY: number): { x: number; y: number } {
    const el = canvasRef.current
    if (!el) return { x: 0, y: 0 }
    const { left, top } = el.getBoundingClientRect()
    const { x: vpX, y: vpY, zoom } = getViewport()
    return {
      x: (clientX - left - vpX) / zoom,
      y: (clientY - top - vpY) / zoom,
    }
  }

  function handleDragOver(e: React.DragEvent<HTMLDivElement>): void {
    if (e.dataTransfer.types.includes(PATHLY_DRAG_MIME)) {
      e.preventDefault()
      e.dataTransfer.dropEffect = 'copy'
    }
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>): void {
    e.preventDefault()
    const raw = e.dataTransfer.getData(PATHLY_DRAG_MIME)
    if (!raw) return
    let payload: PathlyCanvasDragItem
    try {
      const parsed = JSON.parse(raw) as { dragType: string }
      if (parsed.dragType !== 'canvas') return
      payload = parsed as PathlyCanvasDragItem
    } catch {
      return
    }

    const d = dataRef.current
    const nameWithoutExt = payload.name.replace(/\.[^.]+$/, '')

    // If dropped onto an existing state node → assign agent, don't create a new state.
    const target = e.target as HTMLElement
    const stateNodeEl = target.closest('[data-id]') as HTMLElement | null
    const stateId = stateNodeEl?.dataset['id'] ?? null
    if (stateId && d.states.includes(stateId)) {
      onChange({ ...d, agent_map: { ...d.agent_map, [stateId]: nameWithoutExt } })
      return
    }

    // Create a new state centered on the drop cursor.
    const { x, y } = clientToFlow(e.clientX, e.clientY)
    const newId = generateUniqueStateId(payload.name, d.states)
    pendingPositionsRef.current.set(newId, { x: x - NODE_HALF_W, y: y - NODE_HALF_H })
    onChange({
      ...d,
      states: [...d.states, newId],
      agent_map: { ...d.agent_map, [newId]: nameWithoutExt },
      transitions: { ...d.transitions },
    })
  }

  return { handleDragOver, handleDrop }
}
