// Pan/zoom state + handlers for the lightbox's static-SVG view. Wheel zooms (0.5x-8x),
// pointer-drag pans; the lightbox feeds zoom/pan into the .stage via CSS custom properties.

import { useCallback, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'

const MIN_ZOOM = 0.5
const MAX_ZOOM = 8
const clamp = (n: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, n))

export function useSvgPanZoom() {
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const drag = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null)

  // React registers `wheel` listeners as PASSIVE (for scroll perf), so preventDefault() inside a
  // synthetic onWheel is a no-op — the browser logs "Unable to preventDefault inside passive event
  // listener" on every scroll. Attach a NATIVE { passive: false } listener via this ref callback so
  // we can actually cancel the page scroll while zooming. Put `ref={wheelRef}` on the viewport.
  const wheelElRef = useRef<HTMLElement | null>(null)
  const onWheelNative = useCallback((e: WheelEvent) => {
    e.preventDefault()
    setZoom((z) => clamp(z - Math.sign(e.deltaY) * 0.15 * z, MIN_ZOOM, MAX_ZOOM))
  }, [])
  const wheelRef = useCallback(
    (el: HTMLElement | null) => {
      if (wheelElRef.current) wheelElRef.current.removeEventListener('wheel', onWheelNative)
      wheelElRef.current = el
      if (el) el.addEventListener('wheel', onWheelNative, { passive: false })
    },
    [onWheelNative],
  )

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

  return { zoom, pan, wheelRef, onPointerDown, onPointerMove, onPointerUp, reset, zoomIn, zoomOut }
}
