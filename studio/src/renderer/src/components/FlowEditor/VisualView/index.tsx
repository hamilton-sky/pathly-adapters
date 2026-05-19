import { useMemo, useState } from 'react'
import ReactFlow, { Background, Controls, ReactFlowProvider, useReactFlow } from 'reactflow'
import 'reactflow/dist/style.css'
import * as jsYaml from 'js-yaml'
import { useTheme } from '../../../useTheme'
import type { FlowYaml, FlowExportTarget, FlowExportRecord } from '../../../types'
import { PATHLY_DRAG_MIME } from '../../../types'
import type { PathlyCanvasDragItem } from '../../../types'
import { useFlowGraph } from '../hooks/useFlowGraph'
import { makeVisualViewStyles } from './VisualView.styles'
import { NodePanel } from './NodePanel'
import { EdgePanel } from './EdgePanel'
import { StateNode } from './StateNode'
import { validateFlow } from '../utils/validateFlow'
import { useProjectFiles } from '../../../hooks/useProjectFiles'
import { useStore } from '../../../store'
import { writeFile } from '../../../services/pathlyApi'

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

const EXPORT_TARGET_LABELS: Record<FlowExportTarget, string> = {
  pathly: 'Pathly package',
  claude: 'Claude Code',
  codex: 'Codex',
}

function resolveExportPath(target: FlowExportTarget, projectPath: string, flowName: string): string {
  switch (target) {
    case 'pathly': return `${projectPath}/src/pathly_data/core/flows/${flowName}.flow.yaml`
    case 'claude': return `${projectPath}/.claude/pathly-flows/${flowName}.flow.yaml`
    case 'codex':  return `${projectPath}/.codex/pathly-flows/${flowName}.flow.yaml`
  }
}

function VisualViewInner({ data, onChange, onSave }: Props): JSX.Element {
  const t = useTheme()
  const styles = makeVisualViewStyles(t)
  const [detail, setDetail] = useState<PanelDetail>(null)
  const { screenToFlowPosition } = useReactFlow()
  const { sections } = useProjectFiles()
  const { projectPath, selectedItem } = useStore()

  const [exportTarget, setExportTarget] = useState<FlowExportTarget>('pathly')
  const [lastExport, setLastExport] = useState<FlowExportRecord | null>(null)
  const [exportToast, setExportToast] = useState<string | null>(null)
  const [showConfirmModal, setShowConfirmModal] = useState(false)

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

  const hasExportErrors = validationIssues.some((i) => i.severity === 'error')
  const hasExportWarnings = validationIssues.some((i) => i.severity === 'warning')

  function getFlowName(): string {
    if (selectedItem?.name) return selectedItem.name.replace(/\.flow\.yaml$/, '')
    return data.flow ?? 'flow'
  }

  async function doExport(): Promise<void> {
    if (!projectPath) return
    const flowName = getFlowName()
    const targetPath = resolveExportPath(exportTarget, projectPath, flowName)
    const content = jsYaml.dump(data, { lineWidth: 120 })
    try {
      await writeFile(targetPath, content)
      const record: FlowExportRecord = { target: exportTarget, path: targetPath, at: new Date() }
      setLastExport(record)
      setExportToast(`Exported to ${targetPath}`)
      setTimeout(() => setExportToast(null), 4000)
    } catch (err) {
      setExportToast(`Export failed: ${err instanceof Error ? err.message : String(err)}`)
      setTimeout(() => setExportToast(null), 5000)
    }
  }

  function handleExportClick(): void {
    if (hasExportErrors) return
    if (hasExportWarnings) {
      setShowConfirmModal(true)
    } else {
      void doExport()
    }
  }

  function handleConfirmExport(): void {
    setShowConfirmModal(false)
    void doExport()
  }

  const inspectorOpen = detail !== null

  return (
    <div style={styles.wrapper}>
      <div style={styles.toolbar}>
        {/* Layout / authoring controls */}
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

        {/* Divider between layout and export controls */}
        <div style={{ width: 1, height: 20, background: t.bgSurface1, margin: '0 12px', alignSelf: 'center' }} />

        {/* Export controls */}
        <select
          value={exportTarget}
          onChange={(e) => setExportTarget(e.target.value as FlowExportTarget)}
          style={{
            background: t.bgSurface0,
            color: t.textPrimary,
            border: `1px solid ${t.bgSurface1}`,
            borderRadius: 4,
            padding: '3px 8px',
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          {(Object.keys(EXPORT_TARGET_LABELS) as FlowExportTarget[]).map((k) => (
            <option key={k} value={k}>{EXPORT_TARGET_LABELS[k]}</option>
          ))}
        </select>
        <button
          style={{
            ...styles.saveBtn,
            background: hasExportErrors ? t.bgSurface1 : '#8B5CF6',
            color: hasExportErrors ? t.textMuted : '#fff',
            cursor: hasExportErrors ? 'not-allowed' : 'pointer',
            marginLeft: 8,
          }}
          onClick={handleExportClick}
          disabled={hasExportErrors}
          title={hasExportErrors ? 'Fix validation errors before exporting' : 'Export flow'}
        >
          Export
        </button>
      </div>

      {/* Last exported hint */}
      {lastExport && (
        <div style={{ padding: '2px 12px', fontSize: 11, color: t.textMuted, backgroundColor: t.bgMantle, borderBottom: `1px solid ${t.bgSurface0}`, flexShrink: 0 }}>
          Last: {lastExport.path} ✓ {Math.round((Date.now() - lastExport.at.getTime()) / 60000) || '<1'}m ago
        </div>
      )}

      {/* Export toast */}
      {exportToast && (
        <div style={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          background: t.bgSurface1,
          color: t.textPrimary,
          border: `1px solid ${t.bgSurface0}`,
          borderRadius: 6,
          padding: '8px 16px',
          fontSize: 13,
          zIndex: 60,
          boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}>
          {exportToast}
          {lastExport && (
            <button
              style={{ background: 'none', border: 'none', color: t.accent, cursor: 'pointer', fontSize: 12 }}
              onClick={() => { void navigator.clipboard.writeText(lastExport.path) }}
            >
              Copy path
            </button>
          )}
        </div>
      )}

      {/* Warning confirmation modal */}
      {showConfirmModal && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 100,
        }}>
          <div style={{
            background: t.bgMantle, border: `1px solid ${t.bgSurface1}`, borderRadius: 8,
            padding: 24, maxWidth: 400, width: '100%',
          }}>
            <p style={{ color: t.textPrimary, marginBottom: 16, fontSize: 14 }}>
              This flow has validation warnings. Export anyway?
            </p>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                style={{ ...styles.saveBtn, background: t.bgSurface0, color: t.textMuted }}
                onClick={() => setShowConfirmModal(false)}
              >
                Cancel
              </button>
              <button
                style={{ ...styles.saveBtn, background: '#8B5CF6', color: '#fff' }}
                onClick={handleConfirmExport}
              >
                Export anyway
              </button>
            </div>
          </div>
        </div>
      )}

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
