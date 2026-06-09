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
  showHighlights: boolean
  onSelectionComment: (text: string, x: number, y: number) => void
  onResume: (x: number, y: number) => void
}

export function removeAllMarks(container: HTMLElement): void {
  container.querySelectorAll('[data-comment-mark]').forEach((el) => {
    el.parentNode?.replaceChild(document.createTextNode(el.textContent ?? ''), el)
  })
}

function injectMarkForText(container: HTMLElement, searchTerm: string, className: string): HTMLElement | null {
  if (!searchTerm) return null
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null)
  while (walker.nextNode()) {
    const node = walker.currentNode as Text
    const nodeText = node.textContent ?? ''
    let start = nodeText.indexOf(searchTerm)
    let len = searchTerm.length

    if (start === -1) {
      // Whitespace-normalised match (browser adds \n at visual wraps)
      const normNode = nodeText.replace(/\s+/g, ' ')
      const normIdx = normNode.indexOf(searchTerm)
      if (normIdx === -1) continue
      // Map normIdx → original start
      let s = 0, n = 0
      while (s < nodeText.length && n < normIdx) {
        if (/\s/.test(nodeText[s])) { while (s < nodeText.length && /\s/.test(nodeText[s])) s++; n++ }
        else { s++; n++ }
      }
      start = s
      while (s < nodeText.length && n < normIdx + searchTerm.length) {
        if (/\s/.test(nodeText[s])) { while (s < nodeText.length && /\s/.test(nodeText[s])) s++; n++ }
        else { s++; n++ }
      }
      len = s - start
    }

    const mark = document.createElement('mark')
    mark.className = className
    mark.dataset.commentMark = 'true'
    mark.textContent = nodeText.slice(start, start + len)
    const parent = node.parentNode!
    parent.insertBefore(document.createTextNode(nodeText.slice(0, start)), node)
    parent.insertBefore(mark, node)
    parent.insertBefore(document.createTextNode(nodeText.slice(start + len)), node)
    parent.removeChild(node)
    return mark
  }
  return null
}

function injectMark(container: HTMLElement, anchor: string, className: string): HTMLElement | null {
  const norm = anchor.replace(/\s+/g, ' ').trim()
  if (!norm) return null
  // Try full normalised anchor, then progressively shorter prefixes for cross-node selections
  const found = (
    injectMarkForText(container, norm, className) ??
    (norm.length > 60 ? injectMarkForText(container, norm.slice(0, 60), className) : null) ??
    (norm.length > 30 ? injectMarkForText(container, norm.slice(0, 30), className) : null)
  )
  if (found) return found
  const words = norm.split(/\s+/)
  // Fallback A: › -separated chips (priority order list with multiple adjacent <code> elements)
  const chips = norm.split(/\s*›\s*/)
  if (chips.length > 1) {
    for (const chip of chips) {
      const s = chip.trim()
      if (s.length >= 4) {
        const r = injectMarkForText(container, s, className)
        if (r) return r
      }
    }
  }
  // Fallback B: selection STARTS inside a <code> element — strip words from the front
  for (let skip = 1; skip < Math.min(words.length, 8); skip++) {
    const suffix = words.slice(skip).join(' ')
    if (suffix.length >= 8) {
      const r = injectMarkForText(container, suffix, className)
      if (r) return r
    }
  }
  // Fallback C: selection ENDS inside a <code> element — strip words from the end
  for (let take = words.length - 1; take >= Math.max(1, words.length - 8); take--) {
    const prefix = words.slice(0, take).join(' ')
    if (prefix.length >= 8) {
      const r = injectMarkForText(container, prefix, className)
      if (r) return r
    }
  }
  return null
}

export function CommentablePreview({
  content, pendingAnchor, modalOpen, submittedAnchors, showHighlights, onSelectionComment, onResume,
}: Props): JSX.Element {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  // Keep onResume in a ref so the mark-injection effect doesn't re-run just
  // because the parent re-rendered and produced a new function reference.
  const onResumeRef = useRef(onResume)
  useEffect(() => { onResumeRef.current = onResume })

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

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    removeAllMarks(container)
    if (!showHighlights) return

    for (const anchor of submittedAnchors) {
      if (anchor !== pendingAnchor) {
        injectMark(container, anchor, styles.submittedMark)
      }
    }

    if (pendingAnchor && !modalOpen) {
      const mark = injectMark(container, pendingAnchor, styles.pendingMark)
      if (mark) {
        mark.title = 'Click to resume comment'
        mark.style.cursor = 'pointer'
        mark.addEventListener('click', (e) => {
          e.stopPropagation()
          const rect = mark.getBoundingClientRect()
          onResumeRef.current(rect.left + rect.width / 2, rect.bottom)
        })
      }
    }
  }, [pendingAnchor, modalOpen, content, submittedAnchors, showHighlights])

  return (
    <div ref={containerRef} className={styles.root} onMouseUp={handleMouseUp}>
      <MarkdownPreview content={content} />
      {tooltip && (
        <SelectionTooltip x={tooltip.x} y={tooltip.y} onComment={handleComment} />
      )}
    </div>
  )
}
