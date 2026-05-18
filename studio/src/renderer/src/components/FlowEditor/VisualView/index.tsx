import { useMemo, useState } from 'react'
import ReactFlow, { Background, Controls } from 'reactflow'
import 'reactflow/dist/style.css'
import { useTheme } from '../../../useTheme'
import type { FlowYaml } from '../../../types'
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

export function VisualView({ data, onChange, onSave }: Props): JSX.Element {
  const t = useTheme()
  const styles = makeVisualViewStyles(t)
  const [detail, setDetail] = useState<PanelDetail>(null)

  const { nodes, edges, onNodesChange, onEdgesChange, onConnect, onNodeClick, onEdgeClick, handleAgentChange, handleAddTransitionRule, handleAddTransitionAction, dataRef } = useFlowGraph(
    data,
    t,
    onChange,
    (stateId) => setDetail({ type: 'node', stateId }),
    (edgeId, source, target) => setDetail({ type: 'edge', edgeId, source, target })
  )

  const localData = dataRef.current

  return (
    <div style={styles.wrapper}>
      <div style={styles.toolbar}>
        <button style={styles.saveBtn} onClick={onSave}>
          Save
        </button>
      </div>
      <div style={styles.canvas}>
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
