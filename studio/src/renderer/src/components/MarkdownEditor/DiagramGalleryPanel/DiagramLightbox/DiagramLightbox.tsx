// Full-resolution overlay for one diagram. Scroll-wheel zooms, drag pans, Esc or a
// backdrop click closes. The diagram fits the viewport at 100% (see DiagramRender.full)
// and scales up to MAX_ZOOM. Pan/zoom is carried via CSS custom properties (no inline
// transform string). A footer toolbar adds zoom controls, reset, copy-source, and SVG
// export (mermaid only).
//
// Path assumes: src/components/MarkdownEditor/DiagramGalleryPanel/DiagramLightbox/DiagramLightbox.tsx

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import type { DiagramEntry } from '../../diagramTypes'
import DiagramRender from '../DiagramRender/DiagramRender'
import DiagramLightboxToolbar from './DiagramLightboxToolbar/DiagramLightboxToolbar'
import styles from './DiagramLightbox.module.css'

interface Props {
  entry: DiagramEntry
  fileName: string
  onClose: () => void
}

const MIN_ZOOM = 0.5
const MAX_ZOOM = 8

const clamp = (n: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, n))

export default function DiagramLightbox({ entry, fileName, onClose }: Props) {
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const drag = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null)
  const stageRef = useRef<HTMLDivElement>(null)

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

  const resetView = useCallback(() => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
  }, [])

  const zoomIn = useCallback(() => setZoom((z) => clamp(z * 1.25, MIN_ZOOM, MAX_ZOOM)), [])
  const zoomOut = useCallback(() => setZoom((z) => clamp(z / 1.25, MIN_ZOOM, MAX_ZOOM)), [])

  const copySource = useCallback(() => {
    void navigator.clipboard?.writeText(entry.content)
  }, [entry.content])

  const downloadSvg = useCallback(() => {
    const svg = stageRef.current?.querySelector('svg')
    if (!svg) return
    const xml = new XMLSerializer().serializeToString(svg)
    const blob = new Blob([`<?xml version="1.0" encoding="UTF-8"?>\n${xml}`], {
      type: 'image/svg+xml',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${(entry.title || 'diagram').replace(/[^\w.-]+/g, '_')}.svg`
    a.click()
    URL.revokeObjectURL(url)
  }, [entry.title])

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.frame} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <span className={styles.title}>
            {entry.title}
            <span className={styles.file}> — {fileName}</span>
          </span>
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
            ref={stageRef}
            className={styles.stage}
            style={
              { '--tx': `${pan.x}px`, '--ty': `${pan.y}px`, '--zoom': zoom } as React.CSSProperties
            }
          >
            <DiagramRender entry={entry} mode="full" />
          </div>
        </div>

        <div className={styles.footer}>
          <DiagramLightboxToolbar
            zoom={zoom}
            onZoomIn={zoomIn}
            onZoomOut={zoomOut}
            onReset={resetView}
            onCopySource={copySource}
            onDownloadSvg={entry.style === 'mermaid' ? downloadSvg : null}
          />
        </div>
      </div>
    </div>
  )
}
