import { useCallback, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent, RefObject } from 'react'

const POS_KEY = 'pathly:dockPos'

interface Pos { x: number; y: number }

function loadPos(): Pos | null {
  try {
    const v = localStorage.getItem(POS_KEY)
    return v ? (JSON.parse(v) as Pos) : null
  } catch {
    return null
  }
}

function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v))
}

// Pointer-drag for the floating dock. Until the first drag `pos` is null and the dock keeps its
// CSS bottom-right anchor (which auto-fits the collapsed/expanded height). The first drag seeds
// from the dock's current on-screen rect, then tracks the pointer; the position is clamped to the
// viewport, persisted to localStorage, and restored on reload.
export function useDockDrag(anchorRef: RefObject<HTMLElement>): {
  pos: Pos | null
  onGripPointerDown: (e: ReactPointerEvent) => void
} {
  const [pos, setPos] = useState<Pos | null>(loadPos)
  const posRef = useRef<Pos | null>(pos)
  posRef.current = pos

  const onGripPointerDown = useCallback(
    (e: ReactPointerEvent) => {
      if (e.button !== 0) return
      e.preventDefault()
      const rect = anchorRef.current?.getBoundingClientRect()
      const init = posRef.current ?? { x: rect?.left ?? 0, y: rect?.top ?? 0 }
      const startX = e.clientX
      const startY = e.clientY

      const onMove = (ev: PointerEvent): void => {
        const w = anchorRef.current?.offsetWidth ?? 360
        const next: Pos = {
          x: clamp(init.x + (ev.clientX - startX), 0, window.innerWidth - Math.min(w, 120)),
          y: clamp(init.y + (ev.clientY - startY), 0, window.innerHeight - 32),
        }
        posRef.current = next
        setPos(next)
      }
      const onUp = (): void => {
        window.removeEventListener('pointermove', onMove)
        window.removeEventListener('pointerup', onUp)
        if (posRef.current) {
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
