import { useCallback, useEffect, useRef, useState } from 'react'
import ReactFlow, {
  Background,
  Controls,
  addEdge,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type Connection,
  type NodeMouseHandler,
  type EdgeMouseHandler
} from 'reactflow'
import 'reactflow/dist/style.css'
import { useTheme } from '../../useTheme'
import type { Theme } from '../../theme'
import type { FlowYaml } from '../../types'

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

function flowToGraph(data: FlowYaml, t: Theme): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = (data.states ?? []).map((state, i) => ({
    id: state,
    position: { x: i * 220, y: 100 },
    data: {
      label: (
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontWeight: 600, fontSize: '13px' }}>{state}</div>
          <div style={{ fontSize: '11px', color: t.textSecondary, marginTop: '2px' }}>
            {data.agent_map[state] ?? ''}
          </div>
        </div>
      )
    },
    style: {
      backgroundColor: t.bgSurface0,
      border: `1px solid ${t.bgSurface1}`,
      borderRadius: '6px',
      color: t.textPrimary,
      width: 160
    }
  }))

  const edges: Edge[] = []
  let edgeIdx = 0
  for (const [source, targets] of Object.entries(data.transitions ?? {})) {
    for (const target of targets) {
      const edgeId = `e-${edgeIdx++}`
      const rules = data.transition_rules as Record<string, Record<string, string>> | undefined
      let label = 'default'
      if (rules) {
        for (const [artifact, mapping] of Object.entries(rules)) {
          const m = mapping as Record<string, string>
          if (m[source] === target || Object.entries(m).some(([s, tgt]) => s === source && tgt === target)) {
            label = artifact
            break
          }
        }
      }
      edges.push({
        id: edgeId,
        source,
        target,
        label,
        style: { stroke: t.blue },
        labelStyle: { fill: t.textSecondary, fontSize: '11px' },
        labelBgStyle: { fill: t.bgMantle }
      })
    }
  }

  return { nodes, edges }
}

function makeStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    wrapper: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    },
    toolbar: {
      display: 'flex',
      justifyContent: 'flex-end',
      padding: '6px 12px',
      backgroundColor: t.bgMantle,
      borderBottom: `1px solid ${t.bgSurface0}`,
      flexShrink: 0
    },
    saveBtn: {
      background: t.accent,
      border: 'none',
      borderRadius: '4px',
      color: t.bgBase,
      cursor: 'pointer',
      padding: '4px 14px',
      fontSize: '13px',
      fontWeight: 600
    },
    canvas: {
      flex: 1,
      position: 'relative' as const,
      overflow: 'hidden'
    },
    detailPanel: {
      position: 'absolute' as const,
      top: 0,
      right: 0,
      bottom: 0,
      width: '220px',
      zIndex: 10,
      overflowY: 'auto' as const
    }
  }
}

function makePanelStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    panel: {
      backgroundColor: t.bgMantle,
      borderLeft: `1px solid ${t.bgSurface0}`,
      padding: '12px',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px'
    },
    header: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: '4px'
    },
    title: {
      fontWeight: 600,
      fontSize: '13px',
      color: t.accent
    },
    closeBtn: {
      background: 'none',
      border: 'none',
      color: t.textMuted,
      cursor: 'pointer',
      fontSize: '14px',
      padding: '0 4px'
    },
    label: {
      fontSize: '11px',
      color: t.textMuted,
      textTransform: 'uppercase' as const,
      letterSpacing: '0.5px'
    },
    input: {
      backgroundColor: t.bgSurface0,
      border: `1px solid ${t.bgSurface1}`,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: '12px',
      padding: '4px 6px',
      outline: 'none'
    },
    ruleRow: {
      display: 'flex',
      alignItems: 'center',
      gap: '4px',
      fontSize: '12px'
    },
    actionRow: {
      display: 'flex',
      flexDirection: 'column' as const,
      gap: '2px',
      fontSize: '12px'
    },
    ruleArtifact: {
      color: t.green,
      fontSize: '11px',
      wordBreak: 'break-all' as const
    },
    ruleArrow: {
      color: t.textMuted
    },
    ruleTarget: {
      color: t.blue,
      fontSize: '11px'
    },
    addBtn: {
      background: 'none',
      border: `1px dashed ${t.bgSurface1}`,
      borderRadius: '4px',
      color: t.blue,
      cursor: 'pointer',
      fontSize: '12px',
      padding: '4px 8px',
      marginTop: '4px'
    }
  }
}

export function VisualView({ data, onChange, onSave }: Props): JSX.Element {
  const t = useTheme()
  const styles = makeStyles(t)
  const { nodes: initNodes, edges: initEdges } = flowToGraph(data, t)
  const [nodes, , onNodesChange] = useNodesState(initNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initEdges)
  const [detail, setDetail] = useState<PanelDetail>(null)

  const dataRef = useRef(data)
  useEffect(() => { dataRef.current = data }, [data])

  const localData = dataRef.current

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge(connection, eds))
      const { source, target } = connection
      if (!source || !target) return
      const d = dataRef.current
      const existing = d.transitions[source] ?? []
      if (!existing.includes(target)) {
        const updated: FlowYaml = {
          ...d,
          transitions: { ...d.transitions, [source]: [...existing, target] }
        }
        onChange(updated)
      }
    },
    [setEdges, onChange]
  )

  const onNodeClick: NodeMouseHandler = useCallback((_evt, node) => {
    setDetail({ type: 'node', stateId: node.id })
  }, [])

  const onEdgeClick: EdgeMouseHandler = useCallback((_evt, edge) => {
    setDetail({ type: 'edge', edgeId: edge.id, source: edge.source, target: edge.target })
  }, [])

  function handleAgentChange(stateId: string, value: string): void {
    const d = dataRef.current
    const updated: FlowYaml = {
      ...d,
      agent_map: { ...d.agent_map, [stateId]: value }
    }
    onChange(updated)
  }

  function handleAddTransitionRule(source: string): void {
    const d = dataRef.current
    const rules = (d.transition_rules as Record<string, Record<string, string>> | undefined) ?? {}
    const artifact = `artifact_${Date.now()}.md`
    const updated: FlowYaml = {
      ...d,
      transition_rules: { ...rules, [artifact]: { [source]: '' } }
    }
    onChange(updated)
  }

  function handleAddTransitionAction(source: string, target: string): void {
    const d = dataRef.current
    const actions = (d.transition_actions as Record<string, unknown[]> | undefined) ?? {}
    const key = `${source}->${target}`
    const existing = (actions[key] as unknown[] | undefined) ?? []
    const updated: FlowYaml = {
      ...d,
      transition_actions: { ...actions, [key]: [...existing, { skill: '', message: '' }] }
    }
    onChange(updated)
  }

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

interface NodePanelProps {
  stateId: string
  data: FlowYaml
  onAgentChange: (stateId: string, value: string) => void
  onAddRule: (source: string) => void
  onClose: () => void
  t: Theme
}

function NodePanel({ stateId, data, onAgentChange, onAddRule, onClose, t }: NodePanelProps): JSX.Element {
  const panelStyles = makePanelStyles(t)
  const rules = (data.transition_rules as Record<string, Record<string, string>> | undefined) ?? {}
  const relevantRules = Object.entries(rules).filter(([, mapping]) =>
    Object.prototype.hasOwnProperty.call(mapping, stateId)
  )

  return (
    <div style={panelStyles.panel}>
      <div style={panelStyles.header}>
        <span style={panelStyles.title}>{stateId}</span>
        <button style={panelStyles.closeBtn} onClick={onClose}>x</button>
      </div>
      <label style={panelStyles.label}>Agent</label>
      <input
        style={panelStyles.input}
        value={data.agent_map[stateId] ?? ''}
        onChange={(e) => onAgentChange(stateId, e.target.value)}
      />
      <label style={panelStyles.label}>Transition Rules</label>
      {relevantRules.map(([artifact, mapping]) => (
        <div key={artifact} style={panelStyles.ruleRow}>
          <span style={panelStyles.ruleArtifact}>{artifact}</span>
          <span style={panelStyles.ruleArrow}>→</span>
          <span style={panelStyles.ruleTarget}>{mapping[stateId]}</span>
        </div>
      ))}
      <button style={panelStyles.addBtn} onClick={() => onAddRule(stateId)}>
        + Add rule
      </button>
    </div>
  )
}

interface EdgePanelProps {
  source: string
  target: string
  data: FlowYaml
  onAddAction: (source: string, target: string) => void
  onClose: () => void
  t: Theme
}

function EdgePanel({ source, target, data, onAddAction, onClose, t }: EdgePanelProps): JSX.Element {
  const panelStyles = makePanelStyles(t)
  const actions = (data.transition_actions as Record<string, Array<{ skill: string; message: string }>> | undefined) ?? {}
  const key = `${source}->${target}`
  const actionList = actions[key] ?? []

  return (
    <div style={panelStyles.panel}>
      <div style={panelStyles.header}>
        <span style={panelStyles.title}>{source} → {target}</span>
        <button style={panelStyles.closeBtn} onClick={onClose}>x</button>
      </div>
      <label style={panelStyles.label}>Transition Actions</label>
      {actionList.map((action, i) => (
        <div key={i} style={panelStyles.actionRow}>
          <span style={panelStyles.ruleArtifact}>{action.skill || '(skill)'}</span>
          <span style={panelStyles.ruleTarget}>{action.message || '(message)'}</span>
        </div>
      ))}
      <button style={panelStyles.addBtn} onClick={() => onAddAction(source, target)}>
        + Add action
      </button>
    </div>
  )
}
