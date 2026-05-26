import { useState, useRef, useCallback, useEffect } from 'react'

const CHAT_WIDTH_KEY = 'chat-panel-width'
const MIN_WIDTH = 260
const MAX_WIDTH = 720

export function useChatResize(): {
  chatRef: React.RefObject<HTMLDivElement>
  onDragStart: (e: React.MouseEvent) => void
  width: number
} {
  const [width, setWidth] = useState<number>(() => {
    const saved = localStorage.getItem(CHAT_WIDTH_KEY)
    const parsed = saved ? parseInt(saved, 10) : NaN
    return Number.isFinite(parsed) ? Math.min(Math.max(parsed, MIN_WIDTH), MAX_WIDTH) : 320
  })

  const chatRef = useRef<HTMLDivElement>(null)
  const isDraggingRef = useRef(false)
  const startXRef = useRef(0)
  const startWidthRef = useRef(0)

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.style.setProperty('--chat-width', `${width}px`)
    }
  }, [width])

  // Chat panel is on the RIGHT — dragging the left handle:
  // mouse moves LEFT  → clientX decreases → delta < 0 → width increases
  // mouse moves RIGHT → clientX increases → delta > 0 → width decreases
  const onDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isDraggingRef.current = true
    startXRef.current = e.clientX
    startWidthRef.current = width

    function onMouseMove(ev: MouseEvent): void {
      if (!isDraggingRef.current) return
      const delta = startXRef.current - ev.clientX   // inverted: left edge drag
      const next = Math.min(Math.max(startWidthRef.current + delta, MIN_WIDTH), MAX_WIDTH)
      setWidth(next)
    }

    function onMouseUp(): void {
      isDraggingRef.current = false
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      setWidth((w) => { localStorage.setItem(CHAT_WIDTH_KEY, String(w)); return w })
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }, [width])

  return { chatRef, onDragStart, width }
}
