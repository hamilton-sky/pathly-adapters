import { useState } from 'react'
import ReactFlow, { Background, Controls, ReactFlowProvider, useReactFlow } from 'reactflow'
import 'reactflow/dist/style.css'
import { useTheme } from '../../../useTheme'
import type { FlowYaml } from '../../../types'
import { PATHLY_DRAG_MIME } from '../../../types'
import type { PathlyCanvasDragItem } from '../../../types'
import { useFlowGraph } from '../hooks/useFlowGraph'
import { makeVisualViewStyles } from './VisualView.styles'
import { NodePanel } from './NodePanel'
import { EdgePanel } from './EdgePanel'
import { StateNode } from './StateNode'

interface Props {
  data: FlowYaml
  onChange: (updated: FlowYaml) => void
  onSave: () => void
}

interface NodeDetail {
  type: 'node'
  stateId: string
}

interface EdgeDetail {
  type: 'edge'
  edgeId: string
  source: string
  target: string
}

type PanelDetail = NodeDetail | EdgeDetail | null

const nodeTypes = { stateNode: StateNode }

function generateUniqueStateId(base: string, existing: string[]): string {
  const upper = base.replace(/\.[^.]+$/, '').toUpperCase().replace(/[^A-Z0-9_]/g, '_')
  if (!existing.includes(upper)) return upper
  let i = 2
  while (existing.includes(`${upper}_${i}`)) i++
  return `${upper}_${i}`
}

function VisualViewInner({ data, onChange, onSave }: Props): JSX.Element {
  const t = useTheme()
  const styles = makeVisualViewStyles(t)
  const [detail, setDetail] = useState<PanelDetail>(null)
  const { screenToFlowPosition } = useReactFlow()

  const { nodes, edges, onNodesChange, onEdgesChange, onConnect, onNodeClick, onEdgeClick, handleAgentChange, handleAddTransitionRule, handleAddTransitionAction, dataRef } = useFlowGraph(
    data,
    t,
    onChange,
    (stateId) => setDetail({ type: 'node', stateId }),
    (edgeId, source, target) => setDetail({ type: 'edge', edgeId, source, target })
  )

  const localData = dataRef.current

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
    } catch { return }

    const d = dataRef.current
    const nameWithoutExt = payload.name.replace(/\.[^.]+$/, '')

    // Check if drop landed on an existing state node
    const target = e.target as HTMLElement
    const stateNodeEl = target.closest('[data-id]') as HTMLElement | null
    const stateId = stateNodeEl?.dataset['id'] ?? null

    if (stateId && d.states.includes(stateId)) {
      const updated: FlowYaml = {
        ...d,
        agent_map: { ...d.agent_map, [stateId]: nameWithoutExt },
      }
      onChange(updated)
      return
    }

    // Drop on empty canvas — create new state
    const flowPos = screenToFlowPosition({ x: e.clientX, y: e.clientY })
    const newId = generateUniqueStateId(payload.name, d.states)
    const updated: FlowYaml = {
      ...d,
      states: [...d.states, newId],
      agent_map: { ...d.agent_map, [newId]: nameWithoutExt },
      transitions: { ...d.transitions },
    }
    onChange(updated)
    // flowPos is computed but canvas positions are UI-only — the node will be placed
    // by React Flow layout on the next render. We store flowPos for future position persistence.
    void flowPos
  }

  return (
    <div style={styles.wrapper}>
      <div style={styles.toolbar}>
        <button style={styles.saveBtn} onClick={onSave}>
          Save
        </button>
        <button
          style={{ ...styles.saveBtn, background: 'transparent', color: t.textMuted, border: `1px solid ${t.bgSurface1}`, marginLeft: 8 }}
          onClick={() => {
            const d = dataRef.current
            const newId = generateUniqueStateId('STATE', d.states)
            const updated: FlowYaml = { ...d, states: [...d.states, newId], transitions: { ...d.transitions } }
            onChange(updated)
          }}
        >
          + Add state
        </button>
      </div>
      <div
        style={styles.canvas}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onEdgeClick={onEdgeClick}
          fitView
        >
          <Background color={t.bgSurface0} />
          <Controls />
        </ReactFlow>

        {detail && (
          <div style={styles.detailPanel}>
            {detail.type === 'node' && (
              <NodePanel
                stateId={detail.stateId}
                data={localData}
                onAgentChange={handleAgentChange}
                onAddRule={handleAddTransitionRule}
                onClose={() => setDetail(null)}
                t={t}
              />
            )}
            {detail.type === 'edge' && (
              <EdgePanel
                source={detail.source}
                target={detail.target}
                data={localData}
                onAddAction={handleAddTransitionAction}
                onClose={() => setDetail(null)}
                t={t}
              />
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export function VisualView(props: Props): JSX.Element {
  return (
    <ReactFlowProvider>
      <VisualViewInner {...props} />
    </ReactFlowProvider>
  )
}
