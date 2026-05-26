import dagre from '@dagrejs/dagre'
import type { Node, Edge } from 'reactflow'

const NODE_WIDTH = 160
const NODE_HEIGHT = 72

export function applyDagreLayout(
  nodes: Node[],
  edges: Edge[],
  direction: 'LR' | 'TB' = 'TB'
): Node[] {
  const g = new dagre.graphlib.Graph()
  g.setGraph({
    rankdir: direction,
    ranksep: direction === 'TB' ? 80 : 100,
    nodesep: direction === 'TB' ? 80 : 50,
    edgesep: 20,
    marginx: 48,
    marginy: 48,
  })
  g.setDefaultEdgeLabel(() => ({}))

  nodes.forEach((node) => {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
  })

  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target)
  })

  dagre.layout(g)

  return nodes.map((node) => {
    const pos = g.node(node.id)
    return {
      ...node,
      position: {
        x: pos.x - NODE_WIDTH / 2,
        y: pos.y - NODE_HEIGHT / 2,
      },
    }
  })
}
