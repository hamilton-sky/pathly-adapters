import React, { useRef, useState, useEffect } from 'react'
import { MarkdownPreview } from '../MarkdownPreview'
import { SelectionTooltip } from '../SelectionTooltip/SelectionTooltip'
import styles from './CommentablePreview.module.css'

interface TooltipState { x: number; y: number; text: string }

interface Props {
  content: string
  pendingAnchor: string | null
  modalOpen: boolean
  submittedAnchors: string[]
  onSelectionComment: (text: string, x: number, y: number) => void
  onResume: (x: number, y: number) => void
}

function removeAllMarks(container: HTMLElement): void {
  container.querySelectorAll('[data-comment-mark]').forEach((el) => {
    const text = document.createTextNode(el.textContent ?? '')
    el.parentNode?.replaceChild(text, el)
  })
}

function injectMark(container: HTMLElement, anchor: string, className: string): HTMLElement | null {
  const searchText = anchor.split('\n')[0].trim().slice(0, 80)
  if (!searchText) return null
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null)
  while (walker.nextNode()) {
    const node = walker.currentNode as Text
    const nodeText = node.textContent ?? ''
    const idx = nodeText.indexOf(searchText)
    if (idx === -1) continue
    const mark = document.createElement('mark')
    mark.className = className
    mark.dataset.commentMark = 'true'
    mark.textContent = nodeText.slice(idx, idx + searchText.length)
    const parent = node.parentNode!
    parent.insertBefore(document.createTextNode(nodeText.slice(0, idx)), node)
    parent.insertBefore(mark, node)
    parent.insertBefore(document.createTextNode(nodeText.slice(idx + searchText.length)), node)
    parent.removeChild(node)
    return mark
  }
  return null
}

export function CommentablePreview({
  content, pendingAnchor, modalOpen, submittedAnchors, onSelectionComment, onResume,
}: Props): JSX.Element {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  function handleMouseUp(): void {
    const selection = window.getSelection()
    if (!selection || selection.isCollapsed) { setTooltip(null); return }
    const text = selection.toString().trim()
    if (!text) { setTooltip(null); return }
    const range = selection.getRangeAt(0)
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
    window.getSelection()?.removeAllRanges()
    onSelectionComment(tooltip.text, tooltip.x, tooltip.y)
    setTooltip(null)
  }

  // Re-inject all marks whenever anchors or content change
  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    removeAllMarks(container)

    // Submitted comment highlights (persistent, non-interactive)
    for (const anchor of submittedAnchors) {
      if (anchor !== pendingAnchor) {
        injectMark(container, anchor, styles.submittedMark)
      }
    }

    // Pending anchor (interactive — clickable to re-open modal)
    if (pendingAnchor && !modalOpen) {
      const mark = injectMark(container, pendingAnchor, styles.pendingMark)
      if (mark) {
        mark.title = 'Click to resume comment'
        mark.style.cursor = 'pointer'
        mark.addEventListener('click', (e) => {
          e.stopPropagation()
          const rect = mark.getBoundingClientRect()
          onResume(rect.left + rect.width / 2, rect.bottom)
        })
      }
    }
  }, [pendingAnchor, modalOpen, content, submittedAnchors, onResume])

  return (
    <div ref={containerRef} className={styles.root} onMouseUp={handleMouseUp}>
      <MarkdownPreview content={content} />
      {tooltip && (
        <SelectionTooltip x={tooltip.x} y={tooltip.y} onComment={handleComment} />
      )}
    </div>
  )
}
