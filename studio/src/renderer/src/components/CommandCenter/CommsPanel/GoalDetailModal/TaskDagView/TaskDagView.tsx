import { useEffect, useLayoutEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type WheelEvent as ReactWheelEvent } from 'react'
import { createPortal } from 'react-dom'
import { X, ZoomIn, ZoomOut, Maximize2, Minimize2, StickyNote, FileText } from 'lucide-react'
import type { Message } from '../../../types'
import { Tooltip } from '../../../../ui'
import MarkdownRenderer from '../../../../shared/MarkdownRenderer/MarkdownRenderer'
import { CopyTextButton } from '../../../../shared/CopyTextButton/CopyTextButton'
import { dagLayout, type DagNode, type DagOrient, type DagComment } from './dagLayout'
import { edgePath, type Pt } from './edgePath'
import { CommentNode } from './CommentNode/CommentNode'
import s from './TaskDagView.module.css'

const MIN_SCALE = 0.3
const MAX_SCALE = 2.5
const PREVIEW_W = 360
const COMMENT_W = 210
const COMMENT_ANCHOR_Y = 26 // approx mid-handle for edge anchor

function firstLine(text: string): string {
  return text.split('\n').find((l) => l.trim()) ?? text
}
function clampScale(v: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, v))
}

interface Props {
  tasks: Message[]
  order: Message[]
  orient: DagOrient
  comments: DagComment[]
  onCommentsChange: (comments: DagComment[]) => void
  onSaveNote?: (comment: DagComment) => Promise<boolean>
}

export function TaskDagView({ tasks, order, orient, comments, onCommentsChange, onSaveNote }: Props): JSX.Element {
  // `selected` drives the connection highlight + the corner "open text" icon; `previewFor`
  // is the node whose text box is actually open. Selecting highlights only — the box opens
  // on demand via the icon, so the graph stays legible while tracing dependencies.
  const [selected, setSelected] = useState<string | null>(null)
  const [previewFor, setPreviewFor] = useState<string | null>(null)
  const [previewExpanded, setPreviewExpanded] = useState(false)
  const [moved, setMoved] = useState<Record<string, Pt>>({})
  const [view, setView] = useState({ tx: 0, ty: 0, scale: 1 })
  const [panning, setPanning] = useState(false)
  const drag = useRef<{ id: string; sx: number; sy: number; ox: number; oy: number; dragged: boolean } | null>(null)
  const pan = useRef<{ sx: number; sy: number; tx0: number; ty0: number } | null>(null)
  const wrapRef = useRef<HTMLDivElement>(null)

  const layout = useMemo(() => dagLayout(tasks, order, orient), [tasks, order, orient])
  const nodes = useMemo(
    () => layout.nodes.map((n) => ({ ...n, x: moved[n.id]?.x ?? n.x, y: moved[n.id]?.y ?? n.y })),
    [layout, moved],
  )
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes])

  // Center the graph in the viewport on mount and whenever the layout direction changes.
  // useLayoutEffect runs before paint so there's no flash of nodes at (0,0).
  // layout.width/height are read at run-time (not listed as deps) because we only want
  // to re-center on explicit orientation changes, not on every task addition.
  useLayoutEffect(() => {
    setMoved({})
    const wrap = wrapRef.current
    setView({
      tx: wrap ? (wrap.clientWidth - layout.width) / 2 : 0,
      ty: wrap ? (wrap.clientHeight - layout.height) / 2 : 0,
      scale: 1,
    })
  }, [orient]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { setPreviewExpanded(false) }, [previewFor])

  function zoomBy(factor: number): void {
    setView((v) => ({ ...v, scale: clampScale(v.scale * factor) }))
  }
  function resetView(): void {
    const wrap = wrapRef.current
    setView({
      tx: wrap ? (wrap.clientWidth - layout.width) / 2 : 0,
      ty: wrap ? (wrap.clientHeight - layout.height) / 2 : 0,
      scale: 1,
    })
  }

  // ── Node drag ────────────────────────────────────────────────────────────────
  function onNodeDown(e: ReactPointerEvent<HTMLButtonElement>, n: DagNode): void {
    e.stopPropagation()
    const p = moved[n.id] ?? { x: n.x, y: n.y }
    drag.current = { id: n.id, sx: e.clientX, sy: e.clientY, ox: p.x, oy: p.y, dragged: false }
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  function onNodeMove(e: ReactPointerEvent<HTMLButtonElement>): void {
    const d = drag.current
    if (!d) return
    const dx = (e.clientX - d.sx) / view.scale
    const dy = (e.clientY - d.sy) / view.scale
    if (!d.dragged && Math.abs(e.clientX - d.sx) + Math.abs(e.clientY - d.sy) > 4) d.dragged = true
    if (d.dragged) setMoved((prev) => ({ ...prev, [d.id]: { x: d.ox + dx, y: d.oy + dy } }))
  }
  function onNodeUp(e: ReactPointerEvent<HTMLButtonElement>, n: DagNode): void {
    const d = drag.current
    drag.current = null
    try { e.currentTarget.releasePointerCapture(e.pointerId) } catch { /* gone */ }
    if (d && !d.dragged) {
      setSelected((cur) => (cur === n.id ? null : n.id))
      setPreviewFor(null) // a click highlights; the text box opens only via the corner icon
    }
  }

  // ── Canvas pan ───────────────────────────────────────────────────────────────
  function overInteractive(t: HTMLElement): boolean {
    return Boolean(
      t.closest(`.${s.node}`) ||
      t.closest(`.${s.preview}`) ||
      t.closest(`.${s.bottomBar}`) ||
      t.closest('[data-dag-comment]'),
    )
  }
  function onWrapDown(e: ReactPointerEvent<HTMLDivElement>): void {
    if (overInteractive(e.target as HTMLElement)) return
    setSelected(null) // clicking empty canvas clears the highlight…
    setPreviewFor(null) // …and closes the text box
    pan.current = { sx: e.clientX, sy: e.clientY, tx0: view.tx, ty0: view.ty }
    setPanning(true)
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  function onWrapMove(e: ReactPointerEvent<HTMLDivElement>): void {
    const p = pan.current
    if (!p) return
    setView((v) => ({ ...v, tx: p.tx0 + (e.clientX - p.sx), ty: p.ty0 + (e.clientY - p.sy) }))
  }
  function onWrapUp(e: ReactPointerEvent<HTMLDivElement>): void {
    pan.current = null
    setPanning(false)
    try { e.currentTarget.releasePointerCapture(e.pointerId) } catch { /* gone */ }
  }
  function onWheel(e: ReactWheelEvent<HTMLDivElement>): void {
    if (overInteractive(e.target as HTMLElement)) return
    zoomBy(e.deltaY < 0 ? 1.1 : 0.9)
  }

  // Close the open text box on any click outside it. The open-icon is excluded so its own
  // click can (re)open the box; node/canvas clicks fall through to their handlers, which
  // re-select or clear. Selection (the highlight) is intentionally left alone here.
  useEffect(() => {
    if (!previewFor) return
    function onDown(e: MouseEvent): void {
      const el = e.target as HTMLElement | null
      if (el?.closest(`.${s.preview}`) || el?.closest(`.${s.openBtn}`)) return
      setPreviewFor(null)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [previewFor])

  // ── Comment helpers ──────────────────────────────────────────────────────────
  function addComment(): void {
    const wrap = wrapRef.current
    const cx = wrap ? (wrap.clientWidth / 2 - view.tx) / view.scale - COMMENT_W / 2 : 80
    const cy = wrap ? (wrap.clientHeight / 2 - view.ty) / view.scale - 44 : 80
    const id = `cmt-${Date.now()}`
    onCommentsChange([...comments, { id, text: '', color: 'yellow', taskIds: [], x: cx, y: cy }])
  }
  function updateComment(id: string, patch: Partial<Pick<DagComment, 'text' | 'color' | 'taskIds'>>): void {
    onCommentsChange(comments.map((c) => (c.id === id ? { ...c, ...patch } : c)))
  }
  function deleteComment(id: string): void {
    onCommentsChange(comments.filter((c) => c.id !== id))
  }
  function moveComment(id: string, x: number, y: number): void {
    onCommentsChange(comments.map((c) => (c.id === id ? { ...c, x, y } : c)))
  }

  if (tasks.length === 0) return <div className={s.empty}>No tasks to graph yet.</div>

  const sel = selected ? byId.get(selected) ?? null : null
  const previewNode = previewFor ? byId.get(previewFor) ?? null : null
  const previewActualW = previewExpanded ? 520 : PREVIEW_W

  let previewPos: Pt | null = null
  if (previewNode && wrapRef.current) {
    const rect = wrapRef.current.getBoundingClientRect()
    const x = rect.left + previewNode.x * view.scale + view.tx
    const y = rect.top + (previewNode.y + previewNode.h) * view.scale + view.ty + 8
    previewPos = {
      x: Math.max(8, Math.min(x, window.innerWidth - previewActualW - 12)),
      y: Math.max(8, Math.min(y, window.innerHeight - 80)),
    }
  }

  return (
    <>
      <div
        className={s.wrap}
        ref={wrapRef}
        data-panning={panning ? 'true' : 'false'}
        onPointerDown={onWrapDown}
        onPointerMove={onWrapMove}
        onPointerUp={onWrapUp}
        onWheel={onWheel}
      >
        <div
          className={s.canvas}
          style={{ '--cw': `${layout.width}px`, '--ch': `${layout.height}px`, '--tx': `${view.tx}px`, '--ty': `${view.ty}px`, '--scale': view.scale } as React.CSSProperties}
        >
          <svg
            className={s.edges}
            width={layout.width}
            height={layout.height}
            aria-hidden="true"
            data-has-selection={selected ? 'true' : 'false'}
          >
            <defs>
              {/* Arrowhead. fill="context-stroke" makes it inherit each edge's stroke colour
                  (muted / green-done / accent-active) — no per-colour marker needed. */}
              <marker
                id="dag-arrow"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="8"
                markerHeight="8"
                markerUnits="userSpaceOnUse"
                orient="auto"
              >
                <path d="M0,0 L10,5 L0,10 Z" fill="context-stroke" />
              </marker>
            </defs>
            {layout.edges.map((e) => {
              const a = byId.get(e.from)
              const b = byId.get(e.to)
              if (!a || !b) return null
              const active = selected !== null && (e.from === selected || e.to === selected)
              return (
                <path
                  key={`${e.from}->${e.to}`}
                  className={s.edge}
                  data-done={a.task.taskStatus === 'done' ? 'true' : 'false'}
                  data-active={active ? 'true' : 'false'}
                  d={edgePath(a, b)}
                  markerEnd="url(#dag-arrow)"
                />
              )
            })}
            {/* Dashed edges: one per (comment, attached task) pair */}
            {comments.flatMap((c) =>
              c.taskIds.map((tid) => {
                const taskNode = byId.get(tid)
                if (!taskNode) return null
                return (
                  <path
                    key={`cmt-${c.id}-${tid}`}
                    className={s.commentEdge}
                    d={`M${c.x + COMMENT_W / 2},${c.y + COMMENT_ANCHOR_Y} L${taskNode.x + taskNode.w / 2},${taskNode.y + taskNode.h / 2}`}
                  />
                )
              }).filter(Boolean)
            )}
          </svg>

          {nodes.map((n) => (
            <Tooltip key={n.id} label={firstLine(n.task.text)} placement="top" wrap>
              <button
                type="button"
                className={s.node}
                data-status={n.task.taskStatus ?? 'pending'}
                data-selected={selected === n.id ? 'true' : 'false'}
                style={{ '--x': `${n.x}px`, '--y': `${n.y}px`, '--w': `${n.w}px`, '--h': `${n.h}px` } as React.CSSProperties}
                onPointerDown={(e) => onNodeDown(e, n)}
                onPointerMove={onNodeMove}
                onPointerUp={(e) => onNodeUp(e, n)}
              >
                <span className={s.nodeNum}>{n.index}</span>
                <span className={s.nodeText}>{firstLine(n.task.text)}</span>
              </button>
            </Tooltip>
          ))}

          {/* Open-text icon: appears at the selected node's top-right corner. Selecting only
              highlights; this is the explicit affordance to open the task text box. */}
          {sel && (
            <Tooltip label="Open task text" placement="top">
              <button
                type="button"
                className={s.openBtn}
                style={{ '--x': `${sel.x + sel.w}px`, '--y': `${sel.y}px` } as React.CSSProperties}
                onPointerDown={(e) => e.stopPropagation()}
                onClick={(e) => { e.stopPropagation(); setPreviewFor(sel.id) }}
                aria-label="Open task text"
              >
                <FileText size={12} />
              </button>
            </Tooltip>
          )}

          {comments.map((c) => (
            <CommentNode
              key={c.id}
              comment={c}
              tasks={order}
              scale={view.scale}
              onUpdate={updateComment}
              onDelete={deleteComment}
              onMove={moveComment}
              onSave={onSaveNote ? () => onSaveNote(c) : undefined}
            />
          ))}
        </div>

        {/* Bottom bar: zoom controls + Note button — both pinned together bottom-left */}
        <div className={s.bottomBar}>
          <div className={s.zoom}>
            <Tooltip label="Zoom in" placement="top">
              <button type="button" className={s.zoomBtn} onClick={() => zoomBy(1.2)} aria-label="Zoom in"><ZoomIn size={13} /></button>
            </Tooltip>
            <span className={s.zoomPct}>{Math.round(view.scale * 100)}%</span>
            <Tooltip label="Zoom out" placement="top">
              <button type="button" className={s.zoomBtn} onClick={() => zoomBy(1 / 1.2)} aria-label="Zoom out"><ZoomOut size={13} /></button>
            </Tooltip>
            <Tooltip label="Reset view" placement="top">
              <button type="button" className={s.zoomBtn} onClick={resetView} aria-label="Reset view"><Maximize2 size={12} /></button>
            </Tooltip>
          </div>

          <div className={s.noteBar}>
            <Tooltip label="Add sticky note to canvas" placement="top">
              <button type="button" className={s.noteBtn} onClick={addComment} aria-label="Add note">
                <StickyNote size={12} />
                <span>Note</span>
              </button>
            </Tooltip>
            {comments.length > 0 && <span className={s.noteBadge}>{comments.length}</span>}
          </div>
        </div>
      </div>

      {previewNode && previewPos && createPortal(
        <div
          className={s.preview}
          role="dialog"
          aria-label="Task preview"
          data-expanded={previewExpanded ? 'true' : 'false'}
          style={{ '--x': `${previewPos.x}px`, '--y': `${previewPos.y}px` } as React.CSSProperties}
        >
          <div className={s.previewHead}>
            <span className={s.previewStatus} data-status={previewNode.task.taskStatus ?? 'pending'}>
              Task {previewNode.index} · {previewNode.task.taskStatus ?? 'pending'}
            </span>
            <CopyTextButton text={previewNode.task.text} label="task" />
            <Tooltip label={previewExpanded ? 'Collapse text' : 'Expand full text'} placement="left">
              <button
                type="button"
                className={s.previewClose}
                onClick={() => setPreviewExpanded((v) => !v)}
                aria-label={previewExpanded ? 'Collapse preview' : 'Expand preview'}
              >
                {previewExpanded ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
              </button>
            </Tooltip>
            <Tooltip label="Close preview" placement="left">
              <button type="button" className={s.previewClose} onClick={() => setPreviewFor(null)} aria-label="Close preview">
                <X size={13} />
              </button>
            </Tooltip>
          </div>
          <div className={s.previewBody}>
            <MarkdownRenderer content={previewNode.task.text} />
          </div>
        </div>,
        document.body,
      )}
    </>
  )
}
