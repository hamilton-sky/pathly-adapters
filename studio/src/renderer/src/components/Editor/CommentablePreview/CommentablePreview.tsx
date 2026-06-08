import React, { useRef, useState, useEffect } from 'react'
import { MarkdownPreview } from '../MarkdownPreview'
import { SelectionTooltip } from '../SelectionTooltip/SelectionTooltip'
import styles from './CommentablePreview.module.css'

interface TooltipState {
  x: number
  y: number
  text: string
}

interface Props {
  content: string
  onSelectionComment: (anchorText: string) => void
}

export function CommentablePreview({ content, onSelectionComment }: Props): JSX.Element {
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
    function handleDocMouseDown(): void {
      // tooltip's own onMouseDown calls stopPropagation, so this only fires outside it
      setTooltip(null)
    }
    document.addEventListener('mousedown', handleDocMouseDown)
    return () => document.removeEventListener('mousedown', handleDocMouseDown)
  }, [])

  function handleComment(): void {
    if (!tooltip) return
    window.getSelection()?.removeAllRanges()
    onSelectionComment(tooltip.text)
    setTooltip(null)
  }

  return (
    <div ref={containerRef} className={styles.root} onMouseUp={handleMouseUp}>
      <MarkdownPreview content={content} />
      {tooltip && (
        <SelectionTooltip x={tooltip.x} y={tooltip.y} onComment={handleComment} />
      )}
    </div>
  )
}
