import { useMemo, useRef, useState, useCallback } from 'react'
import ReactFlow, { Background, Controls, ReactFlowProvider, useReactFlow, addEdge, updateEdge } from 'reactflow'
import type { Node, Edge, Connection } from 'reactflow'
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
import type { StateNodeData } from '../utils/flowToGraph'
import { validateFlow } from '../utils/validateFlow'
import { resolveExportPath } from '../utils/exportPaths'
import { applyDagreLayout } from '../utils/autoLayout'
import { useProjectFiles } from '../../../hooks/useProjectFiles'
import { useStore } from '../../../store'
import { writeFile } from '../../../services/pathlyApi'
import { Tooltip } from '../../ui'

interface Props {
  data: FlowYaml
  onChange: (updated: FlowYaml) => void
  onSave: () => void
  tab: 'visual' | 'yaml'
  onTabClick: (t: 'visual' | 'yaml') => void
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
  'pathly-package': 'Pathly package',
  'claude-code': 'Claude Code',
  codex: 'Codex',
}

const EXPORT_TARGET_DESCRIPTIONS: Record<FlowExportTarget, string> = {
  'pathly-package': 'This will overwrite the flow in src/pathly_data/core/flows/. The orchestrator will use this flow immediately.',
  'claude-code': 'This will write to .claude/pathly-flows/. Claude Code will pick up the flow on next session start.',
  codex: 'This will write to .codex/pathly-flows/. Codex will pick up the flow on next session start.',
}

function VisualViewInner({ data, onChange, onSave, tab, onTabClick }: Props): JSX.Element {
  const t = useTheme()
  const styles = makeVisualViewStyles(t)
  const [detail, setDetail] = useState<PanelDetail>(null)
  const [nodeCtxMenu, setNodeCtxMenu] = useState<{ x: number; y: number; nodeId: string } | null>(null)
  const [edgeCtxMenu, setEdgeCtxMenu] = useState<{ x: number; y: number; source: string; target: string } | null>(null)
  const { screenToFlowPosition, fitView } = useReactFlow()
  const { sections } = useProjectFiles()
  const { projectPath, selectedItem } = useStore()

  const canvasRef = useRef<HTMLDivElement>(null)
  const pendingPositionsRef = useRef<Map<string, { x: number; y: number }>>(new Map())

  const [exportTarget, setExportTarget] = useState<FlowExportTarget>('pathly-package')
  const [lastExport, setLastExport] = useState<FlowExportRecord | null>(null)
  const [exportToast, setExportToast] = useState<string | null>(null)
  const [showConfirmModal, setShowConfirmModal] = useState(false)

  // Build known behaviors list for validation — core + user global + project-local, including subdirs
  const knownBehaviors = useMemo(() => {
    const all = (s: import('../../../types').SectionState | undefined) => [
      ...(s?.items ?? []),
      ...(s?.subdirs ?? []).flatMap((sd) => sd.files ?? []),
    ]
    const names = [
      ...['Skills', 'UserSkills', 'My Skills'].flatMap((k) => all(sections[k]).map((i) => i.name.replace(/\.[^.]+$/, ''))),
      ...['Agents', 'UserAgents', 'My Agents'].flatMap((k) => all(sections[k]).map((i) => i.name.replace(/\.[^.]+$/, ''))),
    ]
    return [...new Set(names)]
  }, [sections])

  // Run validation on every render (pure function, cheap)
  const validationIssues = useMemo(() => validateFlow(data, knownBehaviors), [data, knownBehaviors])

  const { nodes, edges, onNodesChange, onEdgesChange, onConnect, onNodeClick, onEdgeClick, handleAgentChange, handleAddTransitionRule, handleAddTransitionAction, dataRef, setNodes, setEdges } = useFlowGraph(
    data,
    t,
    onChange,
    (stateId) => setDetail({ type: 'node', stateId }),
    (edgeId, source, target) => setDetail({ type: 'edge', edgeId, source, target }),
    pendingPositionsRef
  )

  const edgeUpdateSuccessful = useRef(true)

  function handleEdgeUpdateStart(): void {
    edgeUpdateSuccessful.current = false
  }

  function handleEdgeUpdate(oldEdge: Edge, newConnection: Connection): void {
    // Always mark successful — onEdgeUpdate only fires when dropped on a valid handle
    edgeUpdateSuccessful.current = true
    // Always update the visual edge first (restores position even if data unchanged)
    setEdges((eds) => updateEdge(oldEdge, newConnection, eds))

    const d = dataRef.current
    const oldSource = oldEdge.source
    const oldTarget = oldEdge.target
    const newSource = newConnection.source ?? oldSource
    const newTarget = newConnection.target ?? oldTarget

    if (oldSource === newSource && oldTarget === newTarget) return

    const newTransitions = { ...d.transitions }
    if (newTransitions[oldSource]) {
      newTransitions[oldSource] = newTransitions[oldSource].filter((t) => t !== oldTarget)
      if (newTransitions[oldSource].length === 0) delete newTransitions[oldSource]
    }
    if (!newTransitions[newSource]) newTransitions[newSource] = []
    if (!newTransitions[newSource].includes(newTarget)) {
      newTransitions[newSource] = [...newTransitions[newSource], newTarget]
    }
    onChange({ ...d, transitions: newTransitions })
  }

  function handleEdgeUpdateEnd(_: MouseEvent | TouchEvent, edge: Edge): void {
    if (!edgeUpdateSuccessful.current) {
      const d = dataRef.current
      const newTransitions = { ...d.transitions }
      if (newTransitions[edge.source]) {
        newTransitions[edge.source] = newTransitions[edge.source].filter((t) => t !== edge.target)
        if (newTransitions[edge.source].length === 0) delete newTransitions[edge.source]
      }
      onChange({ ...d, transitions: newTransitions })
      setEdges((eds) => eds.filter((e) => e.id !== edge.id))
    }
    edgeUpdateSuccessful.current = true
  }

  // Inject validation issues + isStart into node data
  const nodesWithIssues = useMemo(() => nodes.map((node) => {
    const nodeIssues = validationIssues.filter((i) => i.target === 'node' && i.id === node.id)
    const baseData = node.data as Record<string, unknown>
    const isStart = data.states[0] === node.id
    return { ...node, data: { ...baseData, issues: nodeIssues.length > 0 ? nodeIssues : undefined, isStart } }
  }), [nodes, validationIssues, data.states])

  // Inject validation color into edges
  const edgesWithValidation = useMemo(() => edges.map((edge) => {
    const edgeKey = `${edge.source}->${edge.target}`
    const edgeIssues = validationIssues.filter((i) => i.target === 'edge' && i.id === edgeKey)
    if (edgeIssues.length === 0) return edge
    const hasError = edgeIssues.some((i) => i.level === 'error')
    return { ...edge, style: { ...edge.style, stroke: hasError ? t.red : t.yellow } }
  }), [edges, validationIssues, t])

  const localData = dataRef.current

  function handleNodesDelete(deletedNodes: Node[]): void {
    const d = dataRef.current
    const deletedIds = new Set(deletedNodes.map((n) => n.id))

    const states = d.states.filter((s) => !deletedIds.has(s))

    const transitions: Record<string, string[]> = {}
    for (const [src, targets] of Object.entries(d.transitions)) {
      if (deletedIds.has(src)) continue
      const filtered = targets.filter((t) => !deletedIds.has(t))
      transitions[src] = filtered
    }

    const agent_map: Record<string, string> = {}
    for (const [k, v] of Object.entries(d.agent_map)) {
      if (!deletedIds.has(k)) agent_map[k] = v
    }

    const transition_rules: Record<string, unknown> = {}
    if (d.transition_rules) {
      for (const [k, v] of Object.entries(d.transition_rules)) {
        if (!deletedIds.has(k)) transition_rules[k] = v
      }
    }

    const transition_actions: Record<string, unknown> = {}
    if (d.transition_actions) {
      for (const [k, v] of Object.entries(d.transition_actions as Record<string, unknown>)) {
        const isRelated = [...deletedIds].some((id) => k.includes(id))
        if (!isRelated) transition_actions[k] = v
      }
    }

    const updated: FlowYaml = {
      ...d,
      states,
      transitions,
      agent_map,
      ...(d.transition_rules ? { transition_rules } : {}),
      ...(d.transition_actions ? { transition_actions } : {}),
    }
    onChange(updated)
  }

  function handleEdgesDelete(deletedEdges: Edge[]): void {
    const d = dataRef.current
    const newTransitions = { ...d.transitions }
    for (const edge of deletedEdges) {
      const { source, target } = edge
      if (newTransitions[source]) {
        newTransitions[source] = newTransitions[source].filter((t) => t !== target)
        if (newTransitions[source].length === 0) delete newTransitions[source]
      }
    }
    onChange({ ...d, transitions: newTransitions })
  }

  function removeEdge(source: string, target: string): void {
    const d = dataRef.current
    const newTransitions = { ...d.transitions }
    if (newTransitions[source]) {
      newTransitions[source] = newTransitions[source].filter((t) => t !== target)
      if (newTransitions[source].length === 0) delete newTransitions[source]
    }
    const actionKey = `${source}->${target}`
    const newActions = { ...((d.transition_actions as Record<string, unknown>) ?? {}) }
    delete newActions[actionKey]
    onChange({
      ...d,
      transitions: newTransitions,
      transition_actions: Object.keys(newActions).length > 0 ? newActions : undefined,
    })
    setEdges((eds) => eds.filter((e) => !(e.source === source && e.target === target)))
  }

  const handleRenameState = useCallback((oldId: string, newId: string): void => {
    const d = dataRef.current
    const states = d.states.map((s) => s === oldId ? newId : s)
    const transitions: Record<string, string[]> = {}
    for (const [src, targets] of Object.entries(d.transitions ?? {})) {
      transitions[src === oldId ? newId : src] = targets.map((t) => t === oldId ? newId : t)
    }
    const agent_map: Record<string, string> = {}
    for (const [k, v] of Object.entries(d.agent_map ?? {})) {
      agent_map[k === oldId ? newId : k] = v
    }
    const transition_rules: Record<string, unknown> = {}
    if (d.transition_rules) {
      for (const [k, v] of Object.entries(d.transition_rules as Record<string, unknown>)) {
        transition_rules[k === oldId ? newId : k] = v
      }
    }
    const transition_actions: Record<string, unknown> = {}
    if (d.transition_actions) {
      for (const [k, v] of Object.entries(d.transition_actions as Record<string, unknown>)) {
        const newKey = k.split('->').map((part) => part === oldId ? newId : part).join('->')
        transition_actions[newKey] = v
      }
    }
    onChange({
      ...d,
      states,
      transitions,
      agent_map,
      ...(d.transition_rules ? { transition_rules } : {}),
      ...(d.transition_actions ? { transition_actions } : {}),
    })
    setNodes((nds) => nds.map((n): Node<StateNodeData> => n.id !== oldId ? n : {
      ...n,
      id: newId,
      data: { ...n.data, state: newId },
    }))
    setEdges((eds) => eds.map((e) => ({
      ...e,
      ...(e.source === oldId ? { source: newId } : {}),
      ...(e.target === oldId ? { target: newId } : {}),
      id: `${e.source === oldId ? newId : e.source}__${e.target === oldId ? newId : e.target}`,
    })))
    setDetail({ type: 'node', stateId: newId })
  }, [dataRef, onChange, setNodes, setEdges])

  function handleEdgeContextMenu(e: React.MouseEvent, edge: Edge): void {
    e.preventDefault()
    setEdgeCtxMenu({ x: e.clientX, y: e.clientY, source: edge.source, target: edge.target })
  }

  function handleNodeContextMenu(e: React.MouseEvent, node: Node): void {
    e.preventDefault()
    setNodeCtxMenu({ x: e.clientX, y: e.clientY, nodeId: node.id })
  }

  function removeState(stateId: string): void {
    const d = dataRef.current
    const newStates = d.states.filter((s) => s !== stateId)
    const newTransitions: Record<string, string[]> = {}
    for (const [src, targets] of Object.entries(d.transitions ?? {})) {
      if (src === stateId) continue
      const filtered = targets.filter((t) => t !== stateId)
      if (filtered.length > 0) newTransitions[src] = filtered
    }
    const newAgentMap = { ...d.agent_map }
    delete newAgentMap[stateId]
    const newRules = { ...((d.transition_rules as Record<string, unknown> | undefined) ?? {}) }
    delete newRules[stateId]
    const newActions: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(d.transition_actions ?? {})) {
      if (!k.startsWith(`${stateId}->`) && !k.endsWith(`->${stateId}`)) {
        newActions[k] = v
      }
    }
    onChange({
      ...d,
      states: newStates,
      transitions: newTransitions,
      agent_map: newAgentMap,
      transition_rules: Object.keys(newRules).length > 0 ? newRules : undefined,
      transition_actions: Object.keys(newActions).length > 0 ? newActions : undefined,
    })
    setNodes((nds) => nds.filter((n) => n.id !== stateId))
    setEdges((eds) => eds.filter((e) => e.source !== stateId && e.target !== stateId))
  }

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
    pendingPositionsRef.current.set(newId, flowPos)
    onChange({
      ...d,
      states: [...d.states, newId],
      agent_map: { ...d.agent_map, [newId]: nameWithoutExt },
      transitions: { ...d.transitions },
    })
  }

  const hasExportErrors = validationIssues.some((i) => i.level === 'error')
  const hasExportWarnings = validationIssues.some((i) => i.level === 'warning')

  function getFlowName(): string {
    if (selectedItem?.name) return selectedItem.name.replace(/\.flow\.yaml$/, '')
    return data.flow ?? 'flow'
  }

  async function doExport(): Promise<void> {
    if (!projectPath) return
    const flowName = getFlowName()
    const targetPath = resolveExportPath(exportTarget, { projectPath, flowName })
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
        {/* Tab switcher */}
        <Tooltip label="Visual canvas editor" placement="bottom">
          <button style={tab === 'visual' ? styles.tabActive : styles.tab} onClick={() => onTabClick('visual')}>Visual</button>
        </Tooltip>
        <Tooltip label="YAML source editor" placement="bottom">
          <button style={tab === 'yaml' ? styles.tabActive : styles.tab} onClick={() => onTabClick('yaml')}>YAML</button>
        </Tooltip>

        <div style={{ width: 1, height: 20, background: t.bgSurface1, margin: '0 6px', alignSelf: 'center' }} />

        {/* Authoring actions */}
        <Tooltip label="Save flow YAML" shortcut="Ctrl+S" placement="bottom">
          <button style={styles.saveBtn} onClick={onSave}>Save</button>
        </Tooltip>
        <Tooltip label="Add a new state node" placement="bottom">
          <button
            style={{ ...styles.saveBtn, background: 'transparent', color: t.textMuted, border: `1px solid ${t.bgSurface1}` }}
            onClick={() => {
              const d = dataRef.current
              const newId = generateUniqueStateId('STATE', d.states)
              const rect = canvasRef.current?.getBoundingClientRect()
              if (rect) {
                pendingPositionsRef.current.set(newId, screenToFlowPosition({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }))
              }
              onChange({ ...d, states: [...d.states, newId], transitions: { ...d.transitions } })
            }}
          >
            + Add state
          </button>
        </Tooltip>
        <Tooltip label="Auto-arrange nodes left-to-right" placement="bottom">
          <button
            style={{ ...styles.saveBtn, background: 'transparent', color: t.textMuted, border: `1px solid ${t.bgSurface1}` }}
            onClick={() => {
              setNodes((nds) => {
                const laid = applyDagreLayout(nds, edges)
                setTimeout(() => fitView({ duration: 300, padding: 0.15 }), 50)
                return laid
              })
            }}
          >
            Auto-layout
          </button>
        </Tooltip>

        {/* Push publish controls to the right */}
        <div style={{ flex: 1 }} />

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
        <Tooltip
          label={hasExportErrors ? 'Fix validation errors before publishing' : 'Publish flow to YAML'}
          placement="bottom"
        >
          <button
            style={{
              ...styles.saveBtn,
              background: hasExportErrors ? t.bgSurface1 : t.accent,
              color: hasExportErrors ? t.textMuted : t.bgBase,
              cursor: hasExportErrors ? 'not-allowed' : 'pointer',
            }}
            onClick={handleExportClick}
            disabled={hasExportErrors}
          >
            Publish
          </button>
        </Tooltip>
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
            <p style={{ color: t.textPrimary, marginBottom: 8, fontSize: 14 }}>
              This flow has validation warnings. Publish anyway?
            </p>
            <p style={{ color: t.textMuted, marginBottom: 16, fontSize: 12 }}>
              {EXPORT_TARGET_DESCRIPTIONS[exportTarget]}
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
                Publish anyway
              </button>
            </div>
          </div>
        </div>
      )}

      {nodeCtxMenu && (
        <>
          <div
            style={{ position: 'fixed', inset: 0, zIndex: 39 }}
            onClick={() => setNodeCtxMenu(null)}
          />
          <div style={{
            position: 'fixed',
            left: nodeCtxMenu.x,
            top: nodeCtxMenu.y,
            background: t.bgMantle,
            border: `1px solid ${t.bgSurface1}`,
            borderRadius: 6,
            boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
            zIndex: 40,
            minWidth: 160,
            padding: '4px 0',
          }}>
            <button
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: '6px 14px', background: 'none', border: 'none',
                color: t.red, fontSize: 13, cursor: 'pointer',
              }}
              onClick={() => {
                removeState(nodeCtxMenu.nodeId)
                setNodeCtxMenu(null)
                if (detail?.type === 'node' && (detail as NodeDetail).stateId === nodeCtxMenu.nodeId) {
                  setDetail(null)
                }
              }}
            >
              Remove from canvas
            </button>
          </div>
        </>
      )}

      {edgeCtxMenu && (
        <>
          <div
            style={{ position: 'fixed', inset: 0, zIndex: 39 }}
            onClick={() => setEdgeCtxMenu(null)}
          />
          <div style={{
            position: 'fixed',
            left: edgeCtxMenu.x,
            top: edgeCtxMenu.y,
            background: t.bgMantle,
            border: `1px solid ${t.bgSurface1}`,
            borderRadius: 6,
            boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
            zIndex: 40,
            minWidth: 180,
            padding: '4px 0',
          }}>
            <button
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: '6px 14px', background: 'none', border: 'none',
                color: t.red, fontSize: 13, cursor: 'pointer',
              }}
              onClick={() => {
                removeEdge(edgeCtxMenu.source, edgeCtxMenu.target)
                setEdgeCtxMenu(null)
                if (detail?.type === 'edge' &&
                    (detail as EdgeDetail).source === edgeCtxMenu.source &&
                    (detail as EdgeDetail).target === edgeCtxMenu.target) {
                  setDetail(null)
                }
              }}
            >
              Delete connection
            </button>
          </div>
        </>
      )}

      <div style={styles.body}>
        <div
          ref={canvasRef}
          style={{ ...styles.canvas, position: 'relative' }}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          {nodesWithIssues.length === 0 && (
            <div style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              pointerEvents: 'none',
              zIndex: 1,
            }}>
              <div style={{
                border: `2px dashed ${t.bgSurface1}`,
                borderRadius: 12,
                padding: '24px 32px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 8,
              }}>
                <div style={{ fontSize: 13, color: t.textMuted }}>
                  Drag an agent from the library to start
                </div>
                <div style={{ fontSize: 11, color: t.textMuted }}>
                  or click <strong style={{ color: t.textSecondary }}>+ Add state</strong> in the toolbar
                </div>
              </div>
            </div>
          )}
          <ReactFlow
            nodes={nodesWithIssues}
            edges={edgesWithValidation}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onEdgeClick={onEdgeClick}
            onNodesDelete={handleNodesDelete}
            onEdgesDelete={handleEdgesDelete}
            onNodeContextMenu={handleNodeContextMenu}
            onEdgeContextMenu={handleEdgeContextMenu}
            onEdgeUpdateStart={handleEdgeUpdateStart}
            onEdgeUpdate={handleEdgeUpdate}
            onEdgeUpdateEnd={handleEdgeUpdateEnd}
            edgeUpdaterRadius={20}
            deleteKeyCode={['Delete', 'Backspace']}
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
                onRename={handleRenameState}
                onClose={() => setDetail(null)}
                onRemove={() => {
                  const stateId = (detail as NodeDetail).stateId
                  removeState(stateId)
                  setDetail(null)
                }}
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
                onRemove={() => {
                  const d = detail as EdgeDetail
                  removeEdge(d.source, d.target)
                  setDetail(null)
                }}
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

export type { Props as VisualViewProps }
