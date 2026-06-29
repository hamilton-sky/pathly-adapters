import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, Link, Upload, Check } from 'lucide-react'
import type { DagComment, CommentColor } from '../dagLayout'
import type { Message } from '../../../../types'
import s from './CommentNode.module.css'

const COLORS: CommentColor[] = ['yellow', 'blue', 'green', 'pink', 'purple']
const PICKER_W = 240

function firstLine(text: string): string {
  return text.split('\n').find((l) => l.trim()) ?? text
}

interface Props {
  comment: DagComment
  tasks: Message[]
  scale: number
  onUpdate: (id: string, patch: Partial<Pick<DagComment, 'text' | 'color' | 'taskIds'>>) => void
  onDelete: (id: string) => void
  onMove: (id: string, x: number, y: number) => void
  onSave?: () => Promise<boolean>
}

// Sticky note on the DAG canvas. Header = drag handle. Task attachment uses a portaled
// custom multi-select so it escapes the canvas overflow:hidden clip.
export function CommentNode({ comment, tasks, scale, onUpdate, onDelete, onMove, onSave }: Props): JSX.Element {
  const dragRef = useRef<{ sx: number; sy: number; ox: number; oy: number } | null>(null)
  const linkBtnRef = useRef<HTMLButtonElement>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [pickerPos, setPickerPos] = useState<{ x: number; y: number } | null>(null)
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)

  // Reset saved badge whenever content changes (note is dirty again).
  useEffect(() => { setSaved(false) }, [comment.text, comment.taskIds])

  function onHandleDown(e: React.PointerEvent<HTMLDivElement>): void {
    if ((e.target as HTMLElement).closest('button,textarea')) return
    e.stopPropagation()
    dragRef.current = { sx: e.clientX, sy: e.clientY, ox: comment.x, oy: comment.y }
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  function onHandleMove(e: React.PointerEvent<HTMLDivElement>): void {
    if (!dragRef.current) return
    const d = dragRef.current
    onMove(comment.id, d.ox + (e.clientX - d.sx) / scale, d.oy + (e.clientY - d.sy) / scale)
  }
  function onHandleUp(e: React.PointerEvent<HTMLDivElement>): void {
    dragRef.current = null
    try { e.currentTarget.releasePointerCapture(e.pointerId) } catch { /* gone */ }
  }

  async function handleSave(e: React.MouseEvent): Promise<void> {
    e.stopPropagation()
    if (!onSave || saving || saved) return
    setSaving(true)
    const ok = await onSave()
    setSaving(false)
    if (ok) setSaved(true)
  }

  function togglePicker(e: React.MouseEvent): void {
    e.stopPropagation()
    if (pickerOpen) { setPickerOpen(false); return }
    const rect = linkBtnRef.current?.getBoundingClientRect()
    if (rect) {
      setPickerPos({
        x: Math.min(rect.left, window.innerWidth - PICKER_W - 8),
        y: rect.bottom + 4,
      })
    }
    setPickerOpen(true)
  }

  useEffect(() => {
    if (!pickerOpen) return
    function onDown(e: MouseEvent): void {
      if (!(e.target as HTMLElement)?.closest('[data-comment-picker]')) setPickerOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [pickerOpen])

  function toggleTask(tid: string): void {
    const next = comment.taskIds.includes(tid)
      ? comment.taskIds.filter((id) => id !== tid)
      : [...comment.taskIds, tid]
    onUpdate(comment.id, { taskIds: next })
  }
  function toggleAll(): void {
    const allOn = tasks.every((t) => comment.taskIds.includes(t.id))
    onUpdate(comment.id, { taskIds: allOn ? [] : tasks.map((t) => t.id) })
  }

  function attachLabel(): string {
    if (comment.taskIds.length === 0) return 'No link'
    if (comment.taskIds.length === tasks.length && tasks.length > 0) return 'All tasks'
    if (comment.taskIds.length === 1) {
      const t = tasks.find((x) => x.id === comment.taskIds[0])
      if (t) return firstLine(t.text).slice(0, 22)
    }
    return `${comment.taskIds.length} tasks`
  }

  const allChecked = tasks.length > 0 && tasks.every((t) => comment.taskIds.includes(t.id))
  const someChecked = comment.taskIds.length > 0 && !allChecked

  return (
    <div
      className={s.note}
      data-color={comment.color}
      data-dag-comment="true"
      style={{ '--cx': `${comment.x}px`, '--cy': `${comment.y}px` } as React.CSSProperties}
      onPointerDown={(e) => e.stopPropagation()}
    >
      <div
        className={s.handle}
        onPointerDown={onHandleDown}
        onPointerMove={onHandleMove}
        onPointerUp={onHandleUp}
      >
        {/* Color picker */}
        <div className={s.colorRow} aria-label="Note color">
          {COLORS.map((c) => (
            <button
              key={c}
              type="button"
              className={s.colorDot}
              data-color={c}
              data-active={comment.color === c ? 'true' : 'false'}
              onClick={(e) => { e.stopPropagation(); onUpdate(comment.id, { color: c }) }}
              aria-label={`Set color ${c}`}
            />
          ))}
        </div>

        {/* Task attach button */}
        <button
          ref={linkBtnRef}
          type="button"
          className={s.attachBtn}
          data-linked={comment.taskIds.length > 0 ? 'true' : 'false'}
          onClick={togglePicker}
          {...(pickerOpen ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
          aria-label="Attach to tasks"
        >
          <Link size={9} />
          <span className={s.attachLabel}>{attachLabel()}</span>
        </button>

        {onSave && (
          <button
            type="button"
            className={s.saveBtn}
            data-saved={saved ? 'true' : 'false'}
            disabled={saving || !comment.text.trim() || comment.taskIds.length === 0}
            onClick={(e) => { void handleSave(e) }}
            aria-label={saved ? 'Note saved to board' : 'Save note to board'}
          >
            {saved ? <Check size={9} /> : <Upload size={9} />}
          </button>
        )}

        <button
          type="button"
          className={s.delBtn}
          onClick={(e) => { e.stopPropagation(); onDelete(comment.id) }}
          aria-label="Delete note"
        >
          <X size={10} />
        </button>
      </div>

      <textarea
        className={s.text}
        value={comment.text}
        onChange={(e) => onUpdate(comment.id, { text: e.target.value })}
        placeholder="Add a note…"
        onClick={(e) => e.stopPropagation()}
        onPointerDown={(e) => e.stopPropagation()}
      />

      {/* Portal multi-select — escapes canvas overflow:hidden */}
      {pickerOpen && pickerPos && createPortal(
        <div
          className={s.picker}
          data-comment-picker="true"
          style={{ '--px': `${pickerPos.x}px`, '--py': `${pickerPos.y}px` } as React.CSSProperties}
          onPointerDown={(e) => e.stopPropagation()}
        >
          <label className={s.pickerRow} data-all="true">
            <input
              type="checkbox"
              checked={allChecked}
              ref={(el) => { if (el) el.indeterminate = someChecked }}
              onChange={toggleAll}
            />
            <span>All tasks</span>
          </label>
          <div className={s.pickerDiv} />
          {tasks.map((t, i) => (
            <label key={t.id} className={s.pickerRow}>
              <input
                type="checkbox"
                checked={comment.taskIds.includes(t.id)}
                onChange={() => toggleTask(t.id)}
              />
              <span>{i + 1}. {firstLine(t.text).slice(0, 38)}</span>
            </label>
          ))}
        </div>,
        document.body,
      )}
    </div>
  )
}
