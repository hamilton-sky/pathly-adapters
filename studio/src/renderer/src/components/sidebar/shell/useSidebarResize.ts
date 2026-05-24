import { useState, useRef, useCallback, useEffect } from 'react'

const SIDEBAR_WIDTH_KEY = 'sidebar-width'
const MIN_WIDTH = 180
const MAX_WIDTH = 480

export function useSidebarResize(): {
  sidebarRef: React.RefObject<HTMLDivElement>
  onDragStart: (e: React.MouseEvent) => void
} {
  const [sidebarWidth, setSidebarWidth] = useState<number>(() => {
    const saved = localStorage.getItem(SIDEBAR_WIDTH_KEY)
    const parsed = saved ? parseInt(saved, 10) : NaN
    return Number.isFinite(parsed) ? Math.min(Math.max(parsed, MIN_WIDTH), MAX_WIDTH) : 240
  })

  const sidebarRef = useRef<HTMLDivElement>(null)
  const isDraggingRef = useRef(false)
  const startXRef = useRef(0)
  const startWidthRef = useRef(0)

  useEffect(() => {
    sidebarRef.current?.style.setProperty('--sidebar-width', `${sidebarWidth}px`)
  }, [sidebarWidth])

  const onDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isDraggingRef.current = true
    startXRef.current = e.clientX
    startWidthRef.current = sidebarWidth

    function onMouseMove(ev: MouseEvent): void {
      if (!isDraggingRef.current) return
      const delta = ev.clientX - startXRef.current
      const next = Math.min(Math.max(startWidthRef.current + delta, MIN_WIDTH), MAX_WIDTH)
      setSidebarWidth(next)
    }

    function onMouseUp(): void {
      isDraggingRef.current = false
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      setSidebarWidth((w) => { localStorage.setItem(SIDEBAR_WIDTH_KEY, String(w)); return w })
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }, [sidebarWidth])

  return { sidebarRef, onDragStart }
}
