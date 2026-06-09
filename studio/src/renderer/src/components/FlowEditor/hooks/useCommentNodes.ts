import { useEffect } from 'react'
import { useNodesState } from 'reactflow'
import type { FlowYaml, CommentEntry } from '../../../types'

type OnUpdate = (id: string, patch: Partial<Omit<CommentEntry, 'id'>>) => void
type OnDelete = (id: string) => void

function buildCommentNode(c: CommentEntry, onUpdate: OnUpdate, onDelete: OnDelete, states: string[]) {
  return {
    id: `__comment__${c.id}`,
    type: 'commentNode' as const,
    position: { x: c.x, y: c.y },
    draggable: true,
    data: { ...c, onUpdate, onDelete, states },
  }
}

/**
 * Manages comment nodes inside ReactFlow's own state (useNodesState), so their
 * positions are tracked internally during drag — exactly like state nodes.
 * Positions are preserved across data updates; only newly added nodes use the
 * YAML x/y as the initial position.
 */
export function useCommentNodes(
  data: FlowYaml,
  onUpdate: OnUpdate,
  onDelete: OnDelete,
  states: string[],
) {
  const [nodes, setNodes, onNodesChange] = useNodesState(
    (data._comments ?? []).map((c) => buildCommentNode(c, onUpdate, onDelete, states))
  )

  useEffect(() => {
    setNodes((current) => {
      // Preserve ReactFlow-managed positions (set during drag) for existing nodes.
      // Only newly-added comment entries fall back to their stored x/y.
      const posMap = new Map(current.map((n) => [n.id, n.position]))
      return (data._comments ?? []).map((c) => {
        const nodeId = `__comment__${c.id}`
        return {
          ...buildCommentNode(c, onUpdate, onDelete, states),
          position: posMap.get(nodeId) ?? { x: c.x, y: c.y },
        }
      })
    })
  }, [data._comments, onUpdate, onDelete, states, setNodes])

  return { commentNodes: nodes, onCommentNodesChange: onNodesChange }
}
