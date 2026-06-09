import React, { useRef, useEffect } from 'react'
import type { RefObject } from 'react'
import type { Comment } from '../../useComments'
import { resolveRange } from '../highlightUtils'
import styles from './CommentGutter.module.css'

interface Props {
  containerRef: RefObject<HTMLDivElement>
  comments: Comment[]
  rangeMapRef: RefObject<Map<string, Range>>
  showHighlights: boolean
  onScrollTo: (id: string) => void
  /** Ref to the pending range while the comment modal is open */
  draftRangeRef?: RefObject<Range | null>
  /** True while the comment modal is open — triggers the draft badge */
  hasDraft?: boolean
}

export function CommentGutter({
  containerRef, comments, rangeMapRef, showHighlights, onScrollTo,
  draftRangeRef, hasDraft,
}: Props): JSX.Element | null {
  const badgeRefs       = useRef<Map<string, HTMLButtonElement>>(new Map())
  const inlineBadgeRefs = useRef<Map<string, HTMLButtonElement>>(new Map())
  const draftBadgeRef   = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container || !showHighlights) return

    const scrollEl = container.firstElementChild as HTMLElement | null

    function repositionAll(): void {
      const c = containerRef.current
      if (!c) return
      const cache = rangeMapRef.current
      if (!cache) return
      const cRect = c.getBoundingClientRect()
      const gutterTop    = cRect.top    + 11
      const gutterBottom = cRect.bottom - 11

      // ── Left gutter badges ──────────────────────────────────────
      for (const comment of comments) {
        const el = badgeRefs.current.get(comment.id)
        if (!el) continue
        const range = resolveRange(c, comment.id, comment.lineText, cache)
        if (!range) { el.style.setProperty('display', 'none'); continue }
        el.style.removeProperty('display')
        const rect     = range.getBoundingClientRect()
        const rawTop   = rect.top + rect.height / 2
        const clamped  = Math.max(gutterTop, Math.min(gutterBottom, rawTop))
        const isPinned = rawTop < gutterTop || rawTop > gutterBottom
        el.style.setProperty('--badge-top',   `${clamped}px`)
        el.style.setProperty('--badge-left',  `${cRect.left + 6}px`)
        el.style.setProperty('--badge-color', `var(--comment-${comment.color}-swatch)`)
        el.dataset.pinned = String(isPinned)
      }

      // ── Inline end-of-selection chips (right edge) ───────────────
      for (const comment of comments) {
        const el = inlineBadgeRefs.current.get(comment.id)
        if (!el) continue
        const range = resolveRange(c, comment.id, comment.lineText, cache)
        if (!range) { el.style.setProperty('display', 'none'); continue }
        el.style.removeProperty('display')
        const rect    = range.getBoundingClientRect()
        const rawTop  = rect.top + rect.height / 2
        const clamped = Math.max(gutterTop, Math.min(gutterBottom, rawTop))
        el.style.setProperty('--inline-top',   `${clamped}px`)
        el.style.setProperty('--inline-left',  `${rect.right + 4}px`)
        el.style.setProperty('--badge-color',  `var(--comment-${comment.color}-swatch)`)
        el.dataset.pinned = String(rawTop < gutterTop || rawTop > gutterBottom)
      }

      // ── Draft badge (right edge of pending selection) ─────────────
      const draftEl = draftBadgeRef.current
      if (draftEl) {
        const dr = hasDraft ? draftRangeRef?.current : null
        if (!dr) {
          draftEl.style.setProperty('--draft-top',  '-100px')
          draftEl.style.setProperty('--draft-left', '-100px')
        } else {
          try {
            const rect   = dr.getBoundingClientRect()
            const rawTop = rect.top + rect.height / 2
            const top    = Math.max(gutterTop, Math.min(gutterBottom, rawTop))
            draftEl.style.setProperty('--draft-top',  `${top}px`)
            draftEl.style.setProperty('--draft-left', `${rect.right + 4}px`)
          } catch { /* detached range */ }
        }
      }
    }

    repositionAll()

    if (scrollEl) scrollEl.addEventListener('scroll', repositionAll, { passive: true })
    const ro = new ResizeObserver(repositionAll)
    ro.observe(container)

    return () => {
      if (scrollEl) scrollEl.removeEventListener('scroll', repositionAll)
      ro.disconnect()
    }
  }, [comments, showHighlights, hasDraft, containerRef, rangeMapRef, draftRangeRef])

  if (!showHighlights) return null

  return (
    <div className={styles.gutter} aria-hidden="true">

      {/* Left gutter — numbered circles for off-screen navigation */}
      {comments.map((comment, idx) => (
        <button
          key={comment.id}
          type="button"
          className={styles.badge}
          aria-label={`Jump to comment ${idx + 1}`}
          data-comment-id={comment.id}
          onClick={() => onScrollTo(comment.id)}
          ref={(el) => {
            if (el) badgeRefs.current.set(comment.id, el)
            else badgeRefs.current.delete(comment.id)
          }}
        >
          {idx + 1}
        </button>
      ))}

      {/* Inline end-of-selection chips — small number at right edge of each highlight */}
      {comments.map((comment, idx) => (
        <button
          key={`inline-${comment.id}`}
          type="button"
          className={styles.inlineBadge}
          aria-label={`Comment ${idx + 1}`}
          onClick={() => onScrollTo(comment.id)}
          ref={(el) => {
            if (el) inlineBadgeRefs.current.set(comment.id, el)
            else inlineBadgeRefs.current.delete(comment.id)
          }}
        >
          {idx + 1}
        </button>
      ))}

      {/* Draft badge — pulsing indicator while the modal is open */}
      <div ref={draftBadgeRef} className={styles.draftBadge} />

    </div>
  )
}
