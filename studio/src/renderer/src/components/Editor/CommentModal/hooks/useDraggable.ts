import { useCallback, useEffect, useRef } from 'react'

interface DragState {
  startX: number
  startY: number
  baseX: number
  baseY: number
}

/**
 * Makes a fixed-positioned element draggable by a handle.
 * The element must read its position from the --modal-x / --modal-y custom
 * properties (left: var(--modal-x); top: var(--modal-y)). The handle's
 * returned onMouseDown begins a drag that rewrites those properties on pointer
 * move, clamped to the viewport.
 */
export function useDraggable(ref: React.RefObject<HTMLElement>): {
  onHandleMouseDown: (e: React.MouseEvent) => void
} {
  const drag = useRef<DragState | null>(null)

  const onMouseMove = useCallback(
    (e: MouseEvent) => {
      const el = ref.current
      const d = drag.current
      if (!el || !d) return
      const { width, height } = el.getBoundingClientRect()
      const x = Math.max(8, Math.min(d.baseX + (e.clientX - d.startX), window.innerWidth - width - 8))
      const y = Math.max(8, Math.min(d.baseY + (e.clientY - d.startY), window.innerHeight - height - 8))
      el.style.setProperty('--modal-x', `${x}px`)
      el.style.setProperty('--modal-y', `${y}px`)
    },
    [ref],
  )

  const onMouseUp = useCallback(() => {
    drag.current = null
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }, [onMouseMove])

  const onHandleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      const el = ref.current
      if (!el) return
      // Ignore clicks on interactive controls inside the handle (e.g. the close button).
      if ((e.target as HTMLElement).closest('button')) return
      const rect = el.getBoundingClientRect()
      drag.current = { startX: e.clientX, startY: e.clientY, baseX: rect.left, baseY: rect.top }
      document.addEventListener('mousemove', onMouseMove)
      document.addEventListener('mouseup', onMouseUp)
      // Prevents the handle's text from being selected while dragging.
      e.preventDefault()
    },
    [ref, onMouseMove, onMouseUp],
  )

  useEffect(
    () => () => {
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    },
    [onMouseMove, onMouseUp],
  )

  return { onHandleMouseDown }
}
