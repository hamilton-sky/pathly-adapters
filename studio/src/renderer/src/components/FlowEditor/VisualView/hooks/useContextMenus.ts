import { useState } from 'react'
import type { Node, Edge } from 'reactflow'

export interface NodeCtxMenu {
  x: number
  y: number
  nodeId: string
}

export interface EdgeCtxMenu {
  x: number
  y: number
  source: string
  target: string
}

export function useContextMenus() {
  const [nodeCtxMenu, setNodeCtxMenu] = useState<NodeCtxMenu | null>(null)
  const [edgeCtxMenu, setEdgeCtxMenu] = useState<EdgeCtxMenu | null>(null)

  function handleNodeContextMenu(e: React.MouseEvent, node: Node): void {
    e.preventDefault()
    setNodeCtxMenu({ x: e.clientX, y: e.clientY, nodeId: node.id })
  }

  function handleEdgeContextMenu(e: React.MouseEvent, edge: Edge): void {
    e.preventDefault()
    setEdgeCtxMenu({ x: e.clientX, y: e.clientY, source: edge.source, target: edge.target })
  }

  return {
    nodeCtxMenu,
    setNodeCtxMenu,
    edgeCtxMenu,
    setEdgeCtxMenu,
    handleNodeContextMenu,
    handleEdgeContextMenu,
  }
}
