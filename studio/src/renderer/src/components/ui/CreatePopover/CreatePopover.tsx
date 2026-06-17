import { useState, useRef, useEffect, useLayoutEffect } from 'react'
import { createPortal } from 'react-dom'
import s from './CreatePopover.module.css'

/** feature-id slug: lowercase, non-alphanumerics → '-', trimmed. */
export function slugify(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

interface Props {
  /** Trigger element the popover anchors under (its DOMRect drives position). */
  anchorEl: HTMLElement | null
  heading: string
  titleLabel: string
  titlePlaceholder: string
  descLabel: string
  descPlaceholder: string
  /** Show a live slug-ID preview under the title (feature creation). */
  showSlug?: boolean
  submitLabel?: string
  /** Receives the raw title + description; the caller slugifies for features. */
  onSubmit: (title: string, description: string) => void
  onClose: () => void
}

const WIDTH = 300

// A small create-form anchored under its trigger button — lighter than a modal,
// keeps the board visible behind it. Title (+ optional slug preview) + optional
// description; closes on Esc or outside-click. Position is computed from the
// anchor and clamped to the viewport.
export function CreatePopover({
  anchorEl, heading, titleLabel, titlePlaceholder, descLabel, descPlaceholder,
  showSlug = false, submitLabel = 'Create', onSubmit, onClose,
}: Props): JSX.Element | null {
  const cardRef = useRef<HTMLDivElement>(null)
  const [title, setTitle] = useState('')
  const [desc, setDesc] = useState('')
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)

  const canCreate = (showSlug ? slugify(title).length : title.trim().length) > 0

  useLayoutEffect(() => {
    if (!anchorEl) return
    const r = anchorEl.getBoundingClientRect()
    const PAD = 8
    let left = r.right - WIDTH
    if (left + WIDTH > window.innerWidth - PAD) left = window.innerWidth - PAD - WIDTH
    if (left < PAD) left = PAD
    setPos({ top: r.bottom + 6, left })
  }, [anchorEl])

  useEffect(() => {
    function onKey(e: KeyboardEvent): void { if (e.key === 'Escape') onClose() }
    function onDown(e: MouseEvent): void {
      const t = e.target as Node
      if (cardRef.current && !cardRef.current.contains(t) && anchorEl && !anchorEl.contains(t)) onClose()
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onDown)
    }
  }, [onClose, anchorEl])

  function submit(): void {
    if (!canCreate) return
    onSubmit(title.trim(), desc.trim())
  }

  if (!pos) return null

  return createPortal(
    <div ref={cardRef} className={s.card} style={{ top: pos.top, left: pos.left }} role="dialog" aria-label={heading}>
      <p className={s.heading}>{heading}</p>

      <label className={s.label} htmlFor="cp-title">{titleLabel} <span className={s.req}>*</span></label>
      <input
        id="cp-title"
        type="text"
        className={s.input}
        placeholder={titlePlaceholder}
        value={title}
        autoFocus
        autoComplete="off"
        onChange={(e) => setTitle(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
      />
      {showSlug && title.trim().length > 0 && (
        <p className={s.slug}>ID: <code>{slugify(title) || '…'}</code></p>
      )}

      <label className={s.label} htmlFor="cp-desc">{descLabel} <span className={s.opt}>(optional)</span></label>
      <textarea
        id="cp-desc"
        className={s.textarea}
        placeholder={descPlaceholder}
        value={desc}
        rows={2}
        onChange={(e) => setDesc(e.target.value)}
      />

      <div className={s.actions}>
        <button type="button" className={s.cancel} onClick={onClose}>Cancel</button>
        <button type="button" className={s.create} disabled={!canCreate} onClick={submit}>{submitLabel}</button>
      </div>
    </div>,
    document.body,
  )
}
