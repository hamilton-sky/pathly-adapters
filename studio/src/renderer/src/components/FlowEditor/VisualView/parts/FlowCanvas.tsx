import { useRef } from 'react'
import ReactFlow, { Background, Controls } from 'reactflow'
import type { Node, Edge, Connection, NodeMouseHandler, EdgeMouseHandler } from 'reactflow'
import 'reactflow/dist/style.css'
import type { Theme } from '../../../../theme'
import { makeVisualViewStyles } from '../VisualView.styles'
import { nodeTypes } from '../constants'
import { EmptyCanvasHint } from './EmptyCanvasHint'

interface Props {
  nodes: Node[]
  edges: Edge[]
  onNodesChange: (changes: import('reactflow').NodeChange[]) => void
  onEdgesChange: (changes: import('reactflow').EdgeChange[]) => void
  onConnect: (connection: Connection) => void
  onNodeClick: NodeMouseHandler
  onEdgeClick: EdgeMouseHandler
  onNodesDelete: (nodes: Node[]) => void
  onEdgesDelete: (edges: Edge[]) => void
  onNodeContextMenu: (e: React.MouseEvent, node: Node) => void
  onEdgeContextMenu: (e: React.MouseEvent, edge: Edge) => void
  onEdgeUpdateStart: () => void
  onEdgeUpdate: (oldEdge: Edge, newConnection: Connection) => void
  onEdgeUpdateEnd: (e: MouseEvent | TouchEvent, edge: Edge) => void
  onDragOver: (e: React.DragEvent<HTMLDivElement>) => void
  onDrop: (e: React.DragEvent<HTMLDivElement>) => void
  canvasRef: React.RefObject<HTMLDivElement>
  t: Theme
}

export function FlowCanvas({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onNodeClick,
  onEdgeClick,
  onNodesDelete,
  onEdgesDelete,
  onNodeContextMenu,
  onEdgeContextMenu,
  onEdgeUpdateStart,
  onEdgeUpdate,
  onEdgeUpdateEnd,
  onDragOver,
  onDrop,
  canvasRef,
  t,
}: Props): JSX.Element {
  const s = makeVisualViewStyles(t)
  return (
    <div ref={canvasRef} style={s.canvas} onDragOver={onDragOver} onDrop={onDrop}>
      {nodes.length === 0 && <EmptyCanvasHint t={t} />}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        onNodesDelete={onNodesDelete}
        onEdgesDelete={onEdgesDelete}
        onNodeContextMenu={onNodeContextMenu}
        onEdgeContextMenu={onEdgeContextMenu}
        onEdgeUpdateStart={onEdgeUpdateStart}
        onEdgeUpdate={onEdgeUpdate}
        onEdgeUpdateEnd={onEdgeUpdateEnd}
        edgeUpdaterRadius={20}
        deleteKeyCode={['Delete', 'Backspace']}
        fitView
      >
        <Background color={t.bgSurface0} />
        <Controls />
      </ReactFlow>
    </div>
  )
}
