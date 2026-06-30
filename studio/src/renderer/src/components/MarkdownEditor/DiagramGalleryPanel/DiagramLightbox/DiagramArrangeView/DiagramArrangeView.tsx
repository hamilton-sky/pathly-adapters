// Interactive "Arrange" canvas for flowchart/graph Mermaid diagrams: parses the source
// into nodes/edges, dagre-lays them out (or restores a saved layout), and renders a
// draggable React Flow canvas. Reuses Studio's FlowEditor dagre helper. A small toolbar
// re-runs the layout in a chosen direction (TB/LR); "Save layout" persists node positions
// back to the .diagrams.json sidecar.

import React, { useCallback, useMemo, useState } from 'react'
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  useNodesState,
  useEdgesState,
} from 'reactflow'
import type { Node, Edge } from 'reactflow'
import { RefreshCw } from 'lucide-react'
import 'reactflow/dist/style.css'
import { applyDagreLayout } from '../../../../FlowEditor/utils/autoLayout'
import { parseMermaidFlow } from './mermaidFlow'
import styles from './DiagramArrangeView.module.css'

type Layout = Record<string, { x: number; y: number }>

interface Props {
  content: string
  savedLayout?: Layout | null
  onSaveLayout: (layout: Layout) => void
}

// React Flow applies these as the node's inline style — CSS vars resolve against :root,
// so the canvas re-themes with Studio. (Node `style` is React Flow config, not JSX style.)
const NODE_STYLE: React.CSSProperties = {
  background: 'var(--bg-surface1)',
  color: 'var(--text-primary)',
  border: '1px solid var(--border-color)',
  borderRadius: 8,
  fontSize: 12,
  width: 160,
  padding: '6px 10px',
  textAlign: 'center',
  whiteSpace: 'pre-line',
  lineHeight: 1.3,
}

export default function DiagramArrangeView({ content, savedLayout, onSaveLayout }: Props) {
  const initial = useMemo(() => {
    const g = parseMermaidFlow(content)
    const rfNodes: Node[] = g.nodes.map((n) => ({
      id: n.id,
      data: { label: n.label },
      position: { x: 0, y: 0 },
      style: NODE_STYLE,
    }))
    const rfEdges: Edge[] = g.edges.map((e, i) => ({
      id: `e${i}_${e.source}_${e.target}`,
      source: e.source,
      target: e.target,
      label: e.label,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: { stroke: 'var(--text-muted)' },
    }))
    const positioned =
      savedLayout && rfNodes.every((n) => savedLayout[n.id])
        ? rfNodes.map((n) => ({ ...n, position: savedLayout[n.id] }))
        : applyDagreLayout(rfNodes, rfEdges, g.direction)
    return { nodes: positioned, edges: rfEdges, count: g.nodes.length, direction: g.direction }
  }, [content, savedLayout])

  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes)
  const [edges, , onEdgesChange] = useEdgesState(initial.edges)
  const [dir, setDir] = useState<'TB' | 'LR'>(initial.direction)

  const relayout = useCallback(
    (d: 'TB' | 'LR') => {
      setDir(d)
      setNodes((nds) => applyDagreLayout(nds, edges, d))
    },
    [edges, setNodes],
  )

  const save = useCallback(() => {
    const layout: Layout = {}
    nodes.forEach((n) => {
      layout[n.id] = { x: Math.round(n.position.x), y: Math.round(n.position.y) }
    })
    onSaveLayout(layout)
  }, [nodes, onSaveLayout])

  if (initial.count === 0) {
    return <div className={styles.empty}>This diagram type can’t be arranged — use the SVG view.</div>
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.toolbar}>
        <button
          type="button"
          className={styles.dirBtn}
          data-active={dir === 'TB' ? 'true' : 'false'}
          onClick={() => relayout('TB')}
          title="Top-to-bottom layout"
        >
          TB
        </button>
        <button
          type="button"
          className={styles.dirBtn}
          data-active={dir === 'LR' ? 'true' : 'false'}
          onClick={() => relayout('LR')}
          title="Left-to-right layout"
        >
          LR
        </button>
        <button
          type="button"
          className={styles.dirBtn}
          onClick={() => relayout(dir)}
          title="Re-run auto-layout"
          aria-label="Re-run auto-layout"
        >
          <RefreshCw size={12} />
        </button>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodesConnectable={false}
        minZoom={0.2}
        fitView
      >
        <Background variant={BackgroundVariant.Dots} color="rgba(136,153,176,0.22)" gap={26} size={1.2} />
        <Controls showInteractive={false} />
      </ReactFlow>
      <button
        type="button"
        className={styles.save}
        onClick={save}
        title="Persist node positions to the sidecar"
      >
        Save layout
      </button>
    </div>
  )
}
