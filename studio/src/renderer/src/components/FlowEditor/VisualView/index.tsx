import { useMemo, useState } from 'react'
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
import { validateFlow } from '../utils/validateFlow'
import { useProjectFiles } from '../../../hooks/useProjectFiles'

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
  const { sections } = useProjectFiles()

  // Build known behaviors list for validation
  const knownBehaviors = useMemo(() => {
    const skills = sections.Skills.items.map((item) => item.name.replace(/\.[^.]+$/, ''))
    const agents = sections.Agents.items.map((item) => item.name.replace(/\.[^.]+$/, ''))
    return [...skills, ...agents]
  }, [sections])

  // Run validation on every render (pure function, cheap)
  const validationIssues = useMemo(() => validateFlow(data, knownBehaviors), [data, knownBehaviors])

  const { nodes, edges, onNodesChange, onEdgesChange, onConnect, onNodeClick, onEdgeClick, handleAgentChange, handleAddTransitionRule, handleAddTransitionAction, dataRef } = useFlowGraph(
    data,
    t,
    onChange,
    (stateId) => setDetail({ type: 'node', stateId }),
    (edgeId, source, target) => setDetail({ type: 'edge', edgeId, source, target })
  )

  // Inject validation issues into node data
  const nodesWithIssues = useMemo(() => nodes.map((node) => {
    const nodeIssues = validationIssues.filter((i) => i.scope === 'node' && i.key === node.id)
    const baseData = node.data as Record<string, unknown>
    return { ...node, data: { ...baseData, issues: nodeIssues.length > 0 ? nodeIssues : undefined } }
  }), [nodes, validationIssues])

  // Inject validation color into edges
  const edgesWithValidation = useMemo(() => edges.map((edge) => {
    const edgeKey = `${edge.source}->${edge.target}`
    const edgeIssues = validationIssues.filter((i) => i.scope === 'edge' && i.key === edgeKey)
    if (edgeIssues.length === 0) return edge
    const hasError = edgeIssues.some((i) => i.severity === 'error')
    return { ...edge, style: { ...edge.style, stroke: hasError ? t.red : t.yellow } }
  }), [edges, validationIssues, t])

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

    const flowPos = screenToFlowPosition({ x: e.clientX, y: e.clientY })
    const newId = generateUniqueStateId(payload.name, d.states)
    const updated: FlowYaml = {
      ...d,
      states: [...d.states, newId],
      agent_map: { ...d.agent_map, [newId]: nameWithoutExt },
      transitions: { ...d.transitions },
    }
    onChange(updated)
    void flowPos
  }

  const inspectorOpen = detail !== null

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
      <div style={styles.body}>
        <div
          style={styles.canvas}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          <ReactFlow
            nodes={nodesWithIssues}
            edges={edgesWithValidation}
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
        </div>

        {inspectorOpen && (
          <div style={styles.inspectorPane}>
            {detail!.type === 'node' && (
              <NodePanel
                stateId={(detail as NodeDetail).stateId}
                data={localData}
                onAgentChange={handleAgentChange}
                onAddRule={handleAddTransitionRule}
                onClose={() => setDetail(null)}
                t={t}
                issues={validationIssues}
              />
            )}
            {detail!.type === 'edge' && (
              <EdgePanel
                source={(detail as EdgeDetail).source}
                target={(detail as EdgeDetail).target}
                data={localData}
                onAddAction={handleAddTransitionAction}
                onClose={() => setDetail(null)}
                t={t}
                onDataChange={onChange}
                issues={validationIssues}
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
