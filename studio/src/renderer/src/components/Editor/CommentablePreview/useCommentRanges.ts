import { useRef, useEffect, useCallback } from 'react'
import type { RefObject } from 'react'
import type { Comment } from '../useComments'
import {
  clearHighlights,
  applyHighlights,
  applyCommentHighlights,
  resolveRange,
  pulseRange,
} from './highlightUtils'

export function useCommentRanges(
  containerRef: RefObject<HTMLDivElement>,
  comments: Comment[],
  pendingAnchor: string | null,
  pendingRangeRef: RefObject<Range | null>,
  modalOpen: boolean,
  showHighlights: boolean
): {
  rangeMapRef: RefObject<Map<string, Range>>
  scrollToComment: (id: string) => void
} {
  const rangeMapRef = useRef(new Map<string, Range>())
  const activeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const commentsRef = useRef(comments)
  useEffect(() => { commentsRef.current = comments })

  // Stable key for detecting content/comment changes
  const commentsKey = comments.map((c) => `${c.id}:${c.lineText}:${c.resolved}`).join('|')

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    if (!showHighlights) {
      clearHighlights()
      return
    }

    applyHighlights(container, pendingRangeRef.current, pendingAnchor, [], modalOpen)
    applyCommentHighlights(container, comments, rangeMapRef.current, pendingAnchor)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingAnchor, modalOpen, commentsKey, showHighlights])

  const scrollToComment = useCallback((id: string) => {
    const container = containerRef.current
    if (!container) return

    const comment = commentsRef.current.find((c) => c.id === id)
    if (!comment) return

    const range = resolveRange(container, id, comment.lineText, rangeMapRef.current)
    if (!range) return

    // container.root has overflow:hidden — scrollIntoView walks up to find the real
    // scroll ancestor (.previewWrapper inside MarkdownPreview, overflow-y:auto)
    const anchorEl = range.startContainer instanceof Element
      ? (range.startContainer as HTMLElement)
      : range.startContainer.parentElement
    anchorEl?.scrollIntoView({ behavior: 'smooth', block: 'center' })

    if (activeTimeoutRef.current !== null) {
      clearTimeout(activeTimeoutRef.current)
    }
    pulseRange(range, container, comment.color)
    activeTimeoutRef.current = setTimeout(() => {
      activeTimeoutRef.current = null
    }, 310)
  }, [containerRef])

  return { rangeMapRef, scrollToComment }
}
