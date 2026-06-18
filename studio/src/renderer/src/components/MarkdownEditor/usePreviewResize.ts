import { useState, useRef, useCallback, useLayoutEffect } from 'react'

const PREVIEW_WIDTH_KEY = 'preview-panel-width'
const MIN_WIDTH = 260
const MAX_WIDTH = 600

export function usePreviewResize(): {
  previewRef: React.RefObject<HTMLDivElement>
  onDragStart: (e: React.MouseEvent) => void
  width: number
} {
  const [width, setWidth] = useState<number>(() => {
    const saved = localStorage.getItem(PREVIEW_WIDTH_KEY)
    const parsed = saved ? parseInt(saved, 10) : NaN
    return Number.isFinite(parsed) ? Math.min(Math.max(parsed, MIN_WIDTH), MAX_WIDTH) : 344
  })

  const previewRef = useRef<HTMLDivElement>(null)
  const isDraggingRef = useRef(false)
  const startXRef = useRef(0)
  const startWidthRef = useRef(0)

  useLayoutEffect(() => {
    if (previewRef.current) {
      previewRef.current.style.setProperty('--preview-width', `${width}px`)
    }
  }, [width])

  // Preview panel is on the RIGHT — dragging the left handle:
  // mouse moves LEFT  → clientX decreases → delta > 0 → width increases
  // mouse moves RIGHT → clientX increases → delta < 0 → width decreases
  const onDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isDraggingRef.current = true
    startXRef.current = e.clientX
    startWidthRef.current = width

    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'col-resize'

    function onMouseMove(ev: MouseEvent): void {
      if (!isDraggingRef.current) return
      const delta = startXRef.current - ev.clientX
      const next = Math.min(Math.max(startWidthRef.current + delta, MIN_WIDTH), MAX_WIDTH)
      setWidth(next)
    }

    function onMouseUp(): void {
      isDraggingRef.current = false
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      setWidth((w) => { localStorage.setItem(PREVIEW_WIDTH_KEY, String(w)); return w })
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }, [width])

  return { previewRef, onDragStart, width }
}
