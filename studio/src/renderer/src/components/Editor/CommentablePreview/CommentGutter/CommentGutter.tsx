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
}

export function CommentGutter({
  containerRef, comments, rangeMapRef, showHighlights, onScrollTo,
}: Props): JSX.Element | null {
  const badgeRefs = useRef<Map<string, HTMLButtonElement>>(new Map())

  useEffect(() => {
    const container = containerRef.current
    if (!container || !showHighlights) return

    // The actual scroll container is the first child of .root (.previewWrapper inside MarkdownPreview)
    const scrollEl = container.firstElementChild as HTMLElement | null

    function repositionBadges(): void {
      const c = containerRef.current
      if (!c) return
      const cache = rangeMapRef.current
      if (!cache) return
      const cRect = c.getBoundingClientRect()
      // Keep badges within the visible gutter strip (half-badge = 11px margin)
      const gutterTop    = cRect.top    + 11
      const gutterBottom = cRect.bottom - 11

      for (const comment of comments) {
        const el = badgeRefs.current.get(comment.id)
        if (!el) continue
        const range = resolveRange(c, comment.id, comment.lineText, cache)
        if (!range) { el.style.setProperty('display', 'none'); continue }
        el.style.removeProperty('display')
        const rect = range.getBoundingClientRect()
        const rawTop    = rect.top + rect.height / 2
        // Clamp so badges for off-screen text pin to the container edge
        const clampedTop = Math.max(gutterTop, Math.min(gutterBottom, rawTop))
        const isPinned   = rawTop < gutterTop || rawTop > gutterBottom
        el.style.setProperty('--badge-top',  `${clampedTop}px`)
        el.style.setProperty('--badge-left', `${cRect.left + 6}px`)
        el.style.setProperty('--badge-color', `var(--comment-${comment.color}-swatch)`)
        el.dataset.pinned = String(isPinned)
      }
    }

    repositionBadges()

    // Listen on the real scroll element (not .root which has overflow:hidden)
    if (scrollEl) scrollEl.addEventListener('scroll', repositionBadges, { passive: true })
    const ro = new ResizeObserver(repositionBadges)
    ro.observe(container)

    return () => {
      if (scrollEl) scrollEl.removeEventListener('scroll', repositionBadges)
      ro.disconnect()
    }
  }, [comments, showHighlights, containerRef, rangeMapRef])

  if (!showHighlights) return null

  return (
    <div className={styles.gutter} aria-hidden="true">
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
    </div>
  )
}
