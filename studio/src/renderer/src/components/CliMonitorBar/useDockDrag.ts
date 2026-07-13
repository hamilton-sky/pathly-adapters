import { useCallback, useEffect, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent, RefObject } from 'react'

const POS_KEY = 'pathly:dockPos'
const DRAG_THRESHOLD = 4 // px — below this a pointerdown is a click, not a drag

interface Pos { x: number; y: number }

function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v))
}

/** Keep the dock inside the viewport (at least a corner reachable) — never off-screen. */
function clampToViewport(p: Pos): Pos {
  return {
    x: clamp(p.x, 0, Math.max(0, window.innerWidth - 120)),
    y: clamp(p.y, 0, Math.max(0, window.innerHeight - 32)),
  }
}

function loadPos(): Pos | null {
  try {
    const v = localStorage.getItem(POS_KEY)
    if (!v) return null
    const p = JSON.parse(v) as Pos
    if (typeof p?.x !== 'number' || typeof p?.y !== 'number') return null
    return clampToViewport(p) // a previously-saved off-screen position is pulled back on-screen
  } catch {
    return null
  }
}

// Pointer-drag for the floating dock. Until the first drag `pos` is null and the dock keeps its
// CSS bottom-right anchor. A drag only starts once the pointer moves past DRAG_THRESHOLD (so a
// click on the header never nudges/strands the dock), is clamped to the viewport, persisted, and
// re-clamped on window resize.
export function useDockDrag(anchorRef: RefObject<HTMLElement>): {
  pos: Pos | null
  onGripPointerDown: (e: ReactPointerEvent) => void
} {
  const [pos, setPos] = useState<Pos | null>(loadPos)
  const posRef = useRef<Pos | null>(pos)
  posRef.current = pos

  // A shrunk viewport (window resize) must not be able to strand a saved position off-screen.
  useEffect(() => {
    const onResize = (): void => setPos((p) => (p ? clampToViewport(p) : p))
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const onGripPointerDown = useCallback(
    (e: ReactPointerEvent) => {
      if (e.button !== 0) return
      // Whole header is the drag surface — but let its buttons click through.
      if ((e.target as HTMLElement).closest('button')) return
      e.preventDefault()
      const rect = anchorRef.current?.getBoundingClientRect()
      const init = posRef.current ?? { x: rect?.left ?? 0, y: rect?.top ?? 0 }
      const startX = e.clientX
      const startY = e.clientY
      let dragging = false

      const onMove = (ev: PointerEvent): void => {
        const dx = ev.clientX - startX
        const dy = ev.clientY - startY
        if (!dragging && Math.abs(dx) + Math.abs(dy) < DRAG_THRESHOLD) return // ignore click jitter
        dragging = true
        const next = clampToViewport({ x: init.x + dx, y: init.y + dy })
        posRef.current = next
        setPos(next)
      }
      const onUp = (): void => {
        window.removeEventListener('pointermove', onMove)
        window.removeEventListener('pointerup', onUp)
        if (dragging && posRef.current) {
          try { localStorage.setItem(POS_KEY, JSON.stringify(posRef.current)) } catch { /* ignore */ }
        }
      }

      window.addEventListener('pointermove', onMove)
      window.addEventListener('pointerup', onUp)
    },
    [anchorRef],
  )

  return { pos, onGripPointerDown }
}
