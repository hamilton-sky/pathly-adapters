import { useRef } from 'react'
import { useReactFlow } from 'reactflow'
import { useTheme } from '../../../useTheme'
import type { FlowYaml } from '../../../types'
import { useFlowGraph } from '../hooks/useFlowGraph'
import { makeVisualViewStyles } from './VisualView.styles'
import { applyDagreLayout } from '../utils/autoLayout'
import { generateUniqueStateId } from './utils/generateUniqueStateId'
import { useInspectorPanel } from './hooks/useInspectorPanel'
import { useContextMenus } from './hooks/useContextMenus'
import { useEdgeReconnect } from './hooks/useEdgeReconnect'
import { useKnownBehaviors } from './hooks/useKnownBehaviors'
import { useFlowValidation } from './hooks/useFlowValidation'
import { useFlowMutations } from './hooks/useFlowMutations'
import { useFlowExport } from './hooks/useFlowExport'
import { useCanvasDnD } from './hooks/useCanvasDnD'
import { Toolbar } from './parts/Toolbar'
import { LastExportHint } from './parts/LastExportHint'
import { ExportToast } from './parts/ExportToast'
import { ExportConfirmModal } from './parts/ExportConfirmModal'
import { NodeContextMenu } from './parts/NodeContextMenu'
import { EdgeContextMenu } from './parts/EdgeContextMenu'
import { FlowCanvas } from './parts/FlowCanvas'
import { InspectorPane } from './parts/InspectorPane'

interface Props {
  data: FlowYaml
  onChange: (updated: FlowYaml) => void
  onSave: () => void
  tab: 'visual' | 'yaml'
  onTabClick: (t: 'visual' | 'yaml') => void
}

export function VisualViewInner({ data, onChange, onSave, tab, onTabClick }: Props): JSX.Element {
  const t = useTheme()
  const s = makeVisualViewStyles(t)
  const { fitView, getViewport } = useReactFlow()

  const canvasRef = useRef<HTMLDivElement>(null)
  const pendingPositionsRef = useRef<Map<string, { x: number; y: number }>>(new Map())

  const { detail, setDetail } = useInspectorPanel()
  const {
    nodeCtxMenu, setNodeCtxMenu,
    edgeCtxMenu, setEdgeCtxMenu,
    handleNodeContextMenu, handleEdgeContextMenu,
  } = useContextMenus()

  const {
    nodes, edges,
    onNodesChange, onEdgesChange, onConnect,
    onNodeClick, onEdgeClick,
    handleAgentChange, handleAddTransitionAction,
    dataRef, setNodes, setEdges,
  } = useFlowGraph(
    data,
    t,
    onChange,
    (stateId) => setDetail({ type: 'node', stateId }),
    (edgeId, source, target) => setDetail({ type: 'edge', edgeId, source, target }),
    pendingPositionsRef
  )

  const { handleEdgeUpdateStart, handleEdgeUpdate, handleEdgeUpdateEnd } = useEdgeReconnect({
    dataRef,
    onChange,
    setEdges,
  })

  const knownBehaviors = useKnownBehaviors()
  const { validationIssues, nodesWithIssues, edgesWithValidation, hasErrors, hasWarnings } =
    useFlowValidation({ data, knownBehaviors, nodes, edges, t })

  const { removeState, removeEdge, handleRenameState, handleNodesDelete, handleEdgesDelete } =
    useFlowMutations({ dataRef, onChange, setNodes, setEdges, setDetail })

  const {
    exportTarget, setExportTarget,
    lastExport, exportToast, showConfirmModal, setShowConfirmModal,
    handleExportClick, handleConfirmExport,
  } = useFlowExport(data)

  const { handleDragOver, handleDrop } = useCanvasDnD({ dataRef, onChange, pendingPositionsRef, canvasRef })

  function addState(): void {
    const d = dataRef.current
    const newId = generateUniqueStateId('STATE', d.states)
    const el = canvasRef.current
    if (el) {
      const { width, height } = el.getBoundingClientRect()
      const { x: vpX, y: vpY, zoom } = getViewport()
      // Place new node centered in the currently visible canvas area.
      pendingPositionsRef.current.set(newId, {
        x: (width  / 2 - vpX) / zoom - 90,
        y: (height / 2 - vpY) / zoom - 40,
      })
    }
    onChange({ ...d, states: [...d.states, newId], transitions: { ...d.transitions } })
  }

  return (
    <div style={s.wrapper}>
      <Toolbar
        tab={tab}
        onTabClick={onTabClick}
        onSave={onSave}
        onAddState={addState}
        onAutoLayout={() => {
          setNodes((nds) => {
            const laid = applyDagreLayout(nds, edges)
            setTimeout(() => fitView({ duration: 300, padding: 0.15 }), 50)
            return laid
          })
        }}
        exportTarget={exportTarget}
        onTargetChange={setExportTarget}
        hasErrors={hasErrors}
        onPublish={() => handleExportClick(hasErrors, hasWarnings)}
        t={t}
      />

      {lastExport && <LastExportHint lastExport={lastExport} t={t} />}

      {exportToast && <ExportToast message={exportToast} lastExport={lastExport} t={t} />}

      {showConfirmModal && (
        <ExportConfirmModal
          exportTarget={exportTarget}
          onCancel={() => setShowConfirmModal(false)}
          onConfirm={handleConfirmExport}
          t={t}
        />
      )}

      {nodeCtxMenu && (
        <NodeContextMenu
          x={nodeCtxMenu.x}
          y={nodeCtxMenu.y}
          nodeId={nodeCtxMenu.nodeId}
          onClose={() => setNodeCtxMenu(null)}
          onRemove={(nodeId) => {
            removeState(nodeId)
            setNodeCtxMenu(null)
            if (detail?.type === 'node' && detail.stateId === nodeId) setDetail(null)
          }}
          t={t}
        />
      )}

      {edgeCtxMenu && (
        <EdgeContextMenu
          x={edgeCtxMenu.x}
          y={edgeCtxMenu.y}
          source={edgeCtxMenu.source}
          target={edgeCtxMenu.target}
          onClose={() => setEdgeCtxMenu(null)}
          onRemove={(source, target) => {
            removeEdge(source, target)
            setEdgeCtxMenu(null)
            if (detail?.type === 'edge' && detail.source === source && detail.target === target) setDetail(null)
          }}
          t={t}
        />
      )}

      <div style={s.body}>
        <FlowCanvas
          nodes={nodesWithIssues}
          edges={edgesWithValidation}
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
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          canvasRef={canvasRef}
          t={t}
        />

        {detail && (
          <InspectorPane
            detail={detail}
            data={dataRef.current}
            onAgentChange={handleAgentChange}
            onRename={handleRenameState}
            onClose={() => setDetail(null)}
            onRemoveNode={(stateId) => { removeState(stateId) }}
            onRemoveEdge={(source, target) => { removeEdge(source, target) }}
            onAddAction={handleAddTransitionAction}
            onDataChange={onChange}
            validationIssues={validationIssues}
            t={t}
          />
        )}
      </div>
    </div>
  )
}
