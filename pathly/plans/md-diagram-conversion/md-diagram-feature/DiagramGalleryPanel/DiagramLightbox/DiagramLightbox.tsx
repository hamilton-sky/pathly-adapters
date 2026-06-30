// Full-resolution overlay for one diagram. Scroll-wheel zooms 0.5×–4×, drag pans,
// Esc or a backdrop click closes. Pure CSS transform — no zoom/pan library.
//
// Path assumes: src/components/MarkdownEditor/DiagramGalleryPanel/DiagramLightbox/DiagramLightbox.tsx

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import type { DiagramEntry } from '../../diagramTypes'
import DiagramRender from '../DiagramRender/DiagramRender'
import styles from './DiagramLightbox.module.css'

interface Props {
  entry: DiagramEntry
  fileName: string
  onClose: () => void
}

const MIN_ZOOM = 0.5
const MAX_ZOOM = 4

const clamp = (n: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, n))

export default function DiagramLightbox({ entry, fileName, onClose }: Props) {
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const drag = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    setZoom((z) => clamp(z - Math.sign(e.deltaY) * 0.15 * z, MIN_ZOOM, MAX_ZOOM))
  }, [])

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      drag.current = { x: e.clientX, y: e.clientY, ox: pan.x, oy: pan.y }
      ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    },
    [pan],
  )

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (!drag.current) return
    setPan({
      x: drag.current.ox + (e.clientX - drag.current.x),
      y: drag.current.oy + (e.clientY - drag.current.y),
    })
  }, [])

  const onPointerUp = useCallback(() => {
    drag.current = null
  }, [])

  function resetView() {
    setZoom(1)
    setPan({ x: 0, y: 0 })
  }

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.frame} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <span className={styles.title}>
            {entry.title}
            <span className={styles.file}> — {fileName}</span>
          </span>
          <button type="button" className={styles.reset} onClick={resetView}>
            Reset
          </button>
          <button type="button" className={styles.close} onClick={onClose} aria-label="Close (Esc)">
            <X size={14} />
          </button>
        </div>

        <div
          className={styles.viewport}
          onWheel={onWheel}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={onPointerUp}
        >
          <div
            className={styles.stage}
            style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
          >
            <DiagramRender entry={entry} mode="full" />
          </div>
        </div>

        <div className={styles.footer}>
          <span>scroll-wheel: zoom {MIN_ZOOM}×–{MAX_ZOOM}×</span>
          <span>drag: pan</span>
          <span className={styles.zoomReadout}>{Math.round(zoom * 100)}%</span>
        </div>
      </div>
    </div>
  )
}
