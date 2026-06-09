import { useRef, useMemo, useCallback } from 'react'
import { useReactFlow } from 'reactflow'
import type { NodeDragHandler, Node, NodeChange, Connection } from 'reactflow'
import { useTheme } from '../../../useTheme'
import type { FlowYaml, CommentShape, CommentEntry } from '../../../types'
import { useFlowGraph } from '../hooks/useFlowGraph'
import { useFlowComments } from '../hooks/useFlowComments'
import { useCommentNodes } from '../hooks/useCommentNodes'
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
    handleAgentChange, handleAdapterChange, handleSkillChange, handleAddTransitionAction,
    dataRef, setNodes, setEdges,
  } = useFlowGraph(
    data,
    t,
    onChange,
    (stateId) => {
      if (stateId.startsWith('__comment__')) return
      setDetail({ type: 'node', stateId })
    },
    (edgeId, source, target) => {
      if (edgeId.startsWith('__attach__')) return
      setDetail({ type: 'edge', edgeId, source, target })
    },
    pendingPositionsRef
  )

  const { addComment, updateComment, deleteComment, moveComment } = useFlowComments(dataRef, onChange)

  const { handleEdgeUpdateStart, handleEdgeUpdate, handleEdgeUpdateEnd } = useEdgeReconnect({
    dataRef,
    onChange,
    setEdges,
  })

  const knownBehaviors = useKnownBehaviors()
  const { validationIssues, nodesWithIssues, edgesWithValidation, hasErrors, hasWarnings } =
    useFlowValidation({ data, knownBehaviors, nodes, edges, t })

  const { removeState, removeEdge, duplicateState, handleRenameState, handleNodesDelete, handleEdgesDelete } =
    useFlowMutations({ dataRef, onChange, setNodes, setEdges, setDetail, pendingPositionsRef })

  const {
    exportTarget, setExportTarget,
    lastExport, exportToast, showConfirmModal, setShowConfirmModal,
    handleExportClick, handleConfirmExport,
  } = useFlowExport(data)

  const { handleDragOver, handleDrop } = useCanvasDnD({ dataRef, onChange, pendingPositionsRef, canvasRef })

  // Stable callbacks passed into CommentNode data — must not recreate on each render
  const handleCommentUpdate = useCallback(
    (commentId: string, patch: Partial<Omit<CommentEntry, 'id'>>) => updateComment(commentId, patch),
    [updateComment]
  )
  const handleCommentDelete = useCallback(
    (commentId: string) => deleteComment(commentId),
    [deleteComment]
  )

  // Comment nodes managed by their own useNodesState — fixes drag flickering.
  // Positions are tracked inside ReactFlow state during drag; only newly-added
  // comments use the YAML x/y as the initial position.
  const { commentNodes, onCommentNodesChange } = useCommentNodes(
    data, handleCommentUpdate, handleCommentDelete, data.states
  )

  // Merge state-node and comment-node change handlers into one for ReactFlow
  const onAllNodesChange = useCallback((changes: NodeChange[]) => {
    const stateChanges = changes.filter((c) => !('id' in c) || !(c as { id: string }).id.startsWith('__comment__'))
    const commentChanges = changes.filter((c) => 'id' in c && (c as { id: string }).id.startsWith('__comment__'))
    if (stateChanges.length > 0) onNodesChange(stateChanges)
    if (commentChanges.length > 0) onCommentNodesChange(commentChanges)
  }, [onNodesChange, onCommentNodesChange])

  const allNodes = useMemo(
    () => [...nodesWithIssues, ...commentNodes],
    [nodesWithIssues, commentNodes]
  )

  const handleAllConnect = useCallback((connection: Connection) => {
    const { source, target } = connection
    if (!source || !target) return
    if (source.startsWith('__comment__') || target.startsWith('__comment__')) return
    onConnect(connection)
  }, [onConnect])

  const attachEdges = useMemo(() =>
    (data._comments ?? [])
      .filter((c) => c.attachedTo)
      .map((c) => ({
        id: `__attach__${c.id}`,
        source: `__comment__${c.id}`,
        sourceHandle: 'attach-src',
        target: c.attachedTo as string,
        targetHandle: null,
        type: 'straight',
        style: { stroke: 'rgba(150,150,160,0.4)', strokeDasharray: '5 4', strokeWidth: 1.5 },
        markerEnd: undefined,
        selectable: false,
        focusable: false,
        data: { isAttachment: true },
      })),
    [data._comments]
  )

  const allEdges = useMemo(
    () => [...edgesWithValidation, ...attachEdges],
    [edgesWithValidation, attachEdges]
  )

  // Persist drag-stop position back to YAML so it survives save/reload
  const handleNodeDragStop: NodeDragHandler = useCallback((_evt: React.MouseEvent, node: Node) => {
    if (node.id.startsWith('__comment__')) {
      moveComment(node.id.slice('__comment__'.length), node.position.x, node.position.y)
    }
  }, [moveComment])

  function addCommentAtCenter(shape: CommentShape): void {
    const el = canvasRef.current
    if (!el) { addComment(shape, 100, 100); return }
    const { width, height } = el.getBoundingClientRect()
    const { x: vpX, y: vpY, zoom } = getViewport()
    addComment(shape, (width / 2 - vpX) / zoom - 100, (height / 2 - vpY) / zoom - 45)
  }

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
        onAddNote={addCommentAtCenter}
        exportTarget={exportTarget}
        onTargetChange={setExportTarget}
        hasErrors={hasErrors}
        onPublish={() => handleExportClick(hasErrors, hasWarnings)}
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
          onDuplicate={(nodeId) => {
            const srcNode = nodes.find((n) => n.id === nodeId)
            if (srcNode) duplicateState(nodeId, srcNode.position)
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
          nodes={allNodes}
          edges={allEdges}
          onNodesChange={onAllNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={handleAllConnect}
          onNodeClick={onNodeClick}
          onEdgeClick={onEdgeClick}
          onNodesDelete={(deletedNodes) => {
            const stateNodesToDelete = deletedNodes.filter((n) => !n.id.startsWith('__comment__'))
            const commentNodesToDelete = deletedNodes.filter((n) => n.id.startsWith('__comment__'))
            if (stateNodesToDelete.length > 0) handleNodesDelete(stateNodesToDelete)
            commentNodesToDelete.forEach((n) => deleteComment(n.id.slice('__comment__'.length)))
          }}
          onEdgesDelete={(deletedEdges) => {
            const fsmEdges = deletedEdges.filter((e) => !e.id.startsWith('__attach__'))
            if (fsmEdges.length > 0) handleEdgesDelete(fsmEdges)
          }}
          onNodeDragStop={handleNodeDragStop}
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
            onAdapterChange={handleAdapterChange}
            onSkillChange={handleSkillChange}
            onRename={handleRenameState}
            onClose={() => setDetail(null)}
            onRemoveNode={(stateId) => { removeState(stateId) }}
            onRemoveEdge={(source, target) => { removeEdge(source, target) }}
            onAddAction={handleAddTransitionAction}
            onDataChange={onChange}
            onSelectEdge={(source, target) => {
              const edgeId = `${source}-${target}`
              setDetail({ type: 'edge', edgeId, source, target })
            }}
            validationIssues={validationIssues}
            t={t}
          />
        )}
      </div>
    </div>
  )
}
