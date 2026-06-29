import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type WheelEvent as ReactWheelEvent } from 'react'
import { createPortal } from 'react-dom'
import { X, ZoomIn, ZoomOut, Maximize2 } from 'lucide-react'
import type { Message } from '../../../types'
import { Tooltip } from '../../../../ui'
import MarkdownRenderer from '../../../../shared/MarkdownRenderer/MarkdownRenderer'
import { CopyTextButton } from '../../../../shared/CopyTextButton/CopyTextButton'
import { dagLayout, type DagNode, type DagOrient } from './dagLayout'
import s from './TaskDagView.module.css'

const MIN_SCALE = 0.3
const MAX_SCALE = 2.5
const PREVIEW_W = 360

function firstLine(text: string): string {
  return text.split('\n').find((l) => l.trim()) ?? text
}
function clampScale(v: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, v))
}

interface Pt {
  x: number
  y: number
}

// Straight centre-to-centre connector. The opaque nodes paint on top of the edge layer, so the
// visible segment reads as an edge-to-edge link from ANY node position (robust to dragging).
function edgePath(a: { x: number; y: number; w: number; h: number }, b: { x: number; y: number; w: number; h: number }): string {
  return `M${a.x + a.w / 2},${a.y + a.h / 2} L${b.x + b.w / 2},${b.y + b.h / 2}`
}

interface Props {
  tasks: Message[]
  order: Message[]
  // Layout is controlled by the modal toolbar so the layout actions can sit next to the tabs.
  orient: DagOrient
}

// The task DAG as an interactive node graph. Layout (top-down / left-right / snake) is owned by the
// modal. The canvas PANS (drag the background) and ZOOMS (buttons bottom-left, or wheel over the
// background). A node can be DRAGGED to reposition it (edges follow). A plain click (no drag) opens
// a preview popover (portaled above everything) — closed by clicking outside, its ✕, or re-click.
export function TaskDagView({ tasks, order, orient }: Props): JSX.Element {
  const [selected, setSelected] = useState<string | null>(null)
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

  // A layout switch invalidates drag positions (old coords) and the framing — reset both.
  useEffect(() => {
    setMoved({})
    setView({ tx: 0, ty: 0, scale: 1 })
  }, [orient])

  function zoomBy(factor: number): void {
    setView((v) => ({ ...v, scale: clampScale(v.scale * factor) }))
  }
  function resetView(): void {
    setView({ tx: 0, ty: 0, scale: 1 })
  }

  // ── Node drag (screen delta → canvas delta via the current scale) ───────────
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
    if (d.dragged) setMoved((prev) => ({ ...prev, [d.id]: { x: Math.max(0, d.ox + dx), y: Math.max(0, d.oy + dy) } }))
  }
  function onNodeUp(e: ReactPointerEvent<HTMLButtonElement>, n: DagNode): void {
    const d = drag.current
    drag.current = null
    try { e.currentTarget.releasePointerCapture(e.pointerId) } catch { /* gone */ }
    if (d && !d.dragged) setSelected((cur) => (cur === n.id ? null : n.id))
  }

  // ── Canvas pan (drag the background) ────────────────────────────────────────
  function overInteractive(t: HTMLElement): boolean {
    return Boolean(t.closest(`.${s.node}`) || t.closest(`.${s.preview}`) || t.closest(`.${s.zoom}`))
  }
  function onWrapDown(e: ReactPointerEvent<HTMLDivElement>): void {
    if (overInteractive(e.target as HTMLElement)) return
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
    // Zoom is a canvas action — only over the background. Over a node or the preview the wheel
    // belongs to that element (e.g. scrolling the preview text), not the canvas.
    if (overInteractive(e.target as HTMLElement)) return
    zoomBy(e.deltaY < 0 ? 1.1 : 0.9)
  }

  // Close the preview on any mousedown outside it AND outside a node.
  useEffect(() => {
    if (!selected) return
    function onDown(e: MouseEvent): void {
      const el = e.target as HTMLElement | null
      if (!el?.closest(`.${s.preview}`) && !el?.closest(`.${s.node}`)) setSelected(null)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [selected])

  if (tasks.length === 0) return <div className={s.empty}>No tasks to graph yet.</div>

  const sel = selected ? byId.get(selected) ?? null : null

  // Anchor the preview under the selected node IN SCREEN SPACE, then portal it to <body> so it
  // floats above everything — full size (never scaled by the zoom transform) and never clipped by
  // the canvas viewport. Recomputed each render so it tracks the node while panning/zooming.
  let previewPos: Pt | null = null
  if (sel && wrapRef.current) {
    const rect = wrapRef.current.getBoundingClientRect()
    const x = rect.left + sel.x * view.scale + view.tx
    const y = rect.top + (sel.y + sel.h) * view.scale + view.ty + 8
    previewPos = {
      x: Math.max(8, Math.min(x, window.innerWidth - PREVIEW_W - 12)),
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
          <svg className={s.edges} width={layout.width} height={layout.height} aria-hidden="true">
            {layout.edges.map((e) => {
              const a = byId.get(e.from)
              const b = byId.get(e.to)
              if (!a || !b) return null
              return (
                <path
                  key={`${e.from}->${e.to}`}
                  className={s.edge}
                  data-done={a.task.taskStatus === 'done' ? 'true' : 'false'}
                  d={edgePath(a, b)}
                />
              )
            })}
          </svg>

          {nodes.map((n) => (
            <Tooltip key={n.id} label={firstLine(n.task.text)} placement="top">
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
        </div>

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
      </div>

      {sel && previewPos && createPortal(
        <div
          className={s.preview}
          role="dialog"
          aria-label="Task preview"
          style={{ '--x': `${previewPos.x}px`, '--y': `${previewPos.y}px` } as React.CSSProperties}
        >
          <div className={s.previewHead}>
            <span className={s.previewStatus} data-status={sel.task.taskStatus ?? 'pending'}>
              Task {sel.index} · {sel.task.taskStatus ?? 'pending'}
            </span>
            <CopyTextButton text={sel.task.text} label="task" />
            <Tooltip label="Close preview" placement="left">
              <button type="button" className={s.previewClose} onClick={() => setSelected(null)} aria-label="Close preview">
                <X size={13} />
              </button>
            </Tooltip>
          </div>
          <div className={s.previewBody}>
            <MarkdownRenderer content={sel.task.text} />
          </div>
        </div>,
        document.body,
      )}
    </>
  )
}
