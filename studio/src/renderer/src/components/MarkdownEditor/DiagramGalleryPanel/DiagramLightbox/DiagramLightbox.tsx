// Full-resolution overlay for one diagram. Default view is the static SVG with wheel-zoom
// + drag-pan (carried via CSS custom properties — no inline transform string). For
// flowchart/graph mermaid, an "Arrange" toggle swaps in a draggable React Flow canvas
// (DiagramArrangeView); a header Back button returns to the SVG. A maximize button cycles
// the frame through three sizes. Esc or a backdrop click closes.
//
// Path assumes: src/components/MarkdownEditor/DiagramGalleryPanel/DiagramLightbox/DiagramLightbox.tsx

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { X, ArrowLeft, Maximize2 } from 'lucide-react'
import type { DiagramEntry } from '../../diagramTypes'
import DiagramRender from '../DiagramRender/DiagramRender'
import DiagramLightboxToolbar from './DiagramLightboxToolbar/DiagramLightboxToolbar'
import DiagramArrangeView from './DiagramArrangeView/DiagramArrangeView'
import { isArrangeable } from './DiagramArrangeView/mermaidFlow'
import { useSvgPanZoom } from './useSvgPanZoom'
import styles from './DiagramLightbox.module.css'

type Layout = Record<string, { x: number; y: number }>
type Size = 'default' | 'large' | 'full'
const NEXT_SIZE: Record<Size, Size> = { default: 'large', large: 'full', full: 'default' }

interface Props {
  entry: DiagramEntry
  fileName: string
  onClose: () => void
  /** Persist Arrange-mode positions back to the sidecar. */
  onSaveLayout?: (entryId: string, layout: Layout) => void
}

export default function DiagramLightbox({ entry, fileName, onClose, onSaveLayout }: Props) {
  const stageRef = useRef<HTMLDivElement>(null)
  const { zoom, pan, wheelRef, onPointerDown, onPointerMove, onPointerUp, reset, zoomIn, zoomOut } =
    useSvgPanZoom()
  const canArrange = useMemo(() => isArrangeable(entry.style, entry.content), [entry.style, entry.content])
  const [arranging, setArranging] = useState(false)
  const [size, setSize] = useState<Size>('default')

  // SVG is the default view; reset to it whenever the shown diagram changes.
  useEffect(() => setArranging(false), [entry.id])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const copySource = () => {
    void navigator.clipboard?.writeText(entry.content)
  }

  const downloadSvg = () => {
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
  }

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.frame} data-size={size} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          {arranging && (
            <button
              type="button"
              className={styles.back}
              onClick={() => setArranging(false)}
              title="Back to SVG view"
              aria-label="Back to SVG view"
            >
              <ArrowLeft size={14} />
              SVG
            </button>
          )}
          <span className={styles.title}>
            {entry.title}
            <span className={styles.file}> — {fileName}</span>
          </span>
          <button
            type="button"
            className={styles.size}
            onClick={() => setSize((s) => NEXT_SIZE[s])}
            title={`Resize (${size}) — click for ${NEXT_SIZE[size]}`}
            aria-label="Resize"
          >
            <Maximize2 size={13} />
          </button>
          <button type="button" className={styles.close} onClick={onClose} aria-label="Close (Esc)">
            <X size={14} />
          </button>
        </div>

        {arranging && canArrange ? (
          <div className={styles.arrangeArea}>
            <DiagramArrangeView
              key={entry.id}
              content={entry.content}
              savedLayout={entry.layout ?? null}
              onSaveLayout={(l) => onSaveLayout?.(entry.id, l)}
            />
          </div>
        ) : (
          <div
            ref={wheelRef}
            className={styles.viewport}
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
        )}

        <div className={styles.footer}>
          <DiagramLightboxToolbar
            zoom={zoom}
            onZoomIn={zoomIn}
            onZoomOut={zoomOut}
            onReset={reset}
            onCopySource={copySource}
            onDownloadSvg={entry.style === 'mermaid' && !arranging ? downloadSvg : null}
            canArrange={canArrange}
            arranging={arranging}
            onToggleArrange={() => setArranging((v) => !v)}
          />
        </div>
      </div>
    </div>
  )
}
