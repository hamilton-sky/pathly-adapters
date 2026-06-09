import React, { forwardRef, useRef, useState, useEffect, useImperativeHandle, useMemo } from 'react'
import { MarkdownPreview } from '../MarkdownPreview'
import { SelectionTooltip } from '../SelectionTooltip/SelectionTooltip'
import { clearHighlights, resolveRange } from './highlightUtils'
import { useCommentRanges } from './useCommentRanges'
import { useCommentKeyboardNav } from './useCommentKeyboardNav'
import { CommentGutter } from './CommentGutter/CommentGutter'
import type { Comment } from '../useComments'
import styles from './CommentablePreview.module.css'

interface TooltipState { x: number; y: number; text: string }

interface Props {
  content: string
  pendingAnchor: string | null
  modalOpen: boolean
  comments: Comment[]
  showHighlights: boolean
  onSelectionComment: (text: string, x: number, y: number) => void
  onResume: (x: number, y: number) => void
}

export interface CommentablePreviewHandle {
  scrollToComment(id: string): void
  getOrphanedIds(): Set<string>
  /** Called immediately after a comment is submitted — pins the live selection Range in the cache. */
  captureRange(commentId: string): void
}

export const CommentablePreview = forwardRef<CommentablePreviewHandle, Props>(
  function CommentablePreview(
    { content, pendingAnchor, modalOpen, comments, showHighlights, onSelectionComment, onResume },
    ref
  ): JSX.Element {
    const [tooltip, setTooltip] = useState<TooltipState | null>(null)
    const containerRef = useRef<HTMLDivElement>(null)
    const tooltipRangeRef = useRef<Range | null>(null)
    const pendingRangeRef = useRef<Range | null>(null)
    const onResumeRef = useRef(onResume)
    useEffect(() => { onResumeRef.current = onResume })

    const unresolvedComments = useMemo(
      () => comments.filter((c) => !c.resolved),
      [comments]
    )

    const { rangeMapRef, scrollToComment } = useCommentRanges(
      containerRef,
      comments,
      pendingAnchor,
      pendingRangeRef,
      modalOpen,
      showHighlights
    )

    useImperativeHandle(ref, () => ({
      scrollToComment,
      getOrphanedIds(): Set<string> {
        const container = containerRef.current
        const cache = rangeMapRef.current
        if (!container || !cache) return new Set()
        const orphaned = new Set<string>()
        for (const comment of unresolvedComments) {
          const range = resolveRange(container, comment.id, comment.lineText, cache)
          if (!range) orphaned.add(comment.id)
        }
        return orphaned
      },
      captureRange(commentId: string): void {
        const range = pendingRangeRef.current
        if (!range) return
        try {
          if (range.startContainer.isConnected) rangeMapRef.current?.set(commentId, range)
        } catch { /* detached range — skip */ }
      },
    }), [scrollToComment, unresolvedComments, rangeMapRef])

    useCommentKeyboardNav(containerRef, unresolvedComments, scrollToComment)

    function handleMouseUp(): void {
      const selection = window.getSelection()
      if (!selection || selection.isCollapsed) { setTooltip(null); return }
      const text = selection.toString().trim()
      if (!text) { setTooltip(null); return }
      const range = selection.getRangeAt(0)
      tooltipRangeRef.current = range.cloneRange()
      const rect = range.getBoundingClientRect()
      setTooltip({ text, x: rect.left + rect.width / 2, y: rect.top })
    }

    useEffect(() => {
      function onDocMouseDown(): void { setTooltip(null) }
      document.addEventListener('mousedown', onDocMouseDown)
      return () => document.removeEventListener('mousedown', onDocMouseDown)
    }, [])

    function handleComment(): void {
      if (!tooltip) return
      pendingRangeRef.current = tooltipRangeRef.current
      tooltipRangeRef.current = null
      window.getSelection()?.removeAllRanges()
      onSelectionComment(tooltip.text, tooltip.x, tooltip.y)
      setTooltip(null)
    }

    function handleClick(e: React.MouseEvent): void {
      if (!pendingAnchor || modalOpen || !pendingRangeRef.current) return
      try {
        for (const rect of Array.from(pendingRangeRef.current.getClientRects())) {
          if (
            e.clientX >= rect.left && e.clientX <= rect.right &&
            e.clientY >= rect.top && e.clientY <= rect.bottom
          ) {
            e.stopPropagation()
            onResumeRef.current(rect.left + rect.width / 2, rect.bottom)
            return
          }
        }
      } catch { /* Range may be detached after a content re-render */ }
    }

    useEffect(() => {
      if (!pendingAnchor) pendingRangeRef.current = null
    }, [pendingAnchor])

    useEffect(() => () => clearHighlights(), [])

    return (
      <div
        ref={containerRef}
        className={styles.root}
        onMouseUp={handleMouseUp}
        onClick={handleClick}
        tabIndex={0}
      >
        <MarkdownPreview content={content} />
        <CommentGutter
          containerRef={containerRef}
          comments={unresolvedComments}
          rangeMapRef={rangeMapRef}
          showHighlights={showHighlights}
          onScrollTo={scrollToComment}
        />
        {tooltip && (
          <SelectionTooltip x={tooltip.x} y={tooltip.y} onComment={handleComment} />
        )}
      </div>
    )
  }
)
