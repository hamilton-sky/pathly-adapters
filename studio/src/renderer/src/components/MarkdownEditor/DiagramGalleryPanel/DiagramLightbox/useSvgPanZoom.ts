// Pan/zoom state + handlers for the lightbox's static-SVG view. Wheel zooms (0.5x-8x),
// pointer-drag pans; the lightbox feeds zoom/pan into the .stage via CSS custom properties.

import { useCallback, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from 'react'

const MIN_ZOOM = 0.5
const MAX_ZOOM = 8
const clamp = (n: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, n))

export function useSvgPanZoom() {
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const drag = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null)

  const onWheel = useCallback((e: ReactWheelEvent) => {
    e.preventDefault()
    setZoom((z) => clamp(z - Math.sign(e.deltaY) * 0.15 * z, MIN_ZOOM, MAX_ZOOM))
  }, [])

  const onPointerDown = useCallback(
    (e: ReactPointerEvent) => {
      drag.current = { x: e.clientX, y: e.clientY, ox: pan.x, oy: pan.y }
      ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    },
    [pan],
  )

  const onPointerMove = useCallback((e: ReactPointerEvent) => {
    if (!drag.current) return
    setPan({
      x: drag.current.ox + (e.clientX - drag.current.x),
      y: drag.current.oy + (e.clientY - drag.current.y),
    })
  }, [])

  const onPointerUp = useCallback(() => {
    drag.current = null
  }, [])

  const reset = useCallback(() => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
  }, [])

  const zoomIn = useCallback(() => setZoom((z) => clamp(z * 1.25, MIN_ZOOM, MAX_ZOOM)), [])
  const zoomOut = useCallback(() => setZoom((z) => clamp(z / 1.25, MIN_ZOOM, MAX_ZOOM)), [])

  return { zoom, pan, onWheel, onPointerDown, onPointerMove, onPointerUp, reset, zoomIn, zoomOut }
}
