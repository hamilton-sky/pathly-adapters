// Footer action bar for the diagram lightbox: zoom controls, reset, copy-source, SVG
// export (mermaid), and (in SVG view) an "Arrange" button that opens the React Flow canvas.
// Exiting Arrange is handled by the lightbox header's Back button. Self-contained — owns
// its transient "copied" feedback.
//
// Path assumes:
//   src/components/MarkdownEditor/DiagramGalleryPanel/DiagramLightbox/DiagramLightboxToolbar/DiagramLightboxToolbar.tsx

import React, { useState } from 'react'
import { ZoomIn, ZoomOut, RotateCcw, Copy, Check, Download, Workflow } from 'lucide-react'
import styles from './DiagramLightboxToolbar.module.css'

interface Props {
  zoom: number
  onZoomIn: () => void
  onZoomOut: () => void
  onReset: () => void
  onCopySource: () => void
  /** Null for non-mermaid styles (no rendered SVG to export). */
  onDownloadSvg: (() => void) | null
  /** Diagram is a flowchart/graph mermaid that can be arranged. */
  canArrange: boolean
  arranging: boolean
  onToggleArrange: () => void
}

export default function DiagramLightboxToolbar({
  zoom,
  onZoomIn,
  onZoomOut,
  onReset,
  onCopySource,
  onDownloadSvg,
  canArrange,
  arranging,
  onToggleArrange,
}: Props) {
  const [copied, setCopied] = useState(false)

  const copy = () => {
    onCopySource()
    setCopied(true)
    setTimeout(() => setCopied(false), 1200)
  }

  return (
    <div className={styles.bar}>
      {!arranging && (
        <>
          <button type="button" className={styles.icon} onClick={onZoomOut} aria-label="Zoom out" title="Zoom out">
            <ZoomOut size={14} />
          </button>
          <span className={styles.readout}>{Math.round(zoom * 100)}%</span>
          <button type="button" className={styles.icon} onClick={onZoomIn} aria-label="Zoom in" title="Zoom in">
            <ZoomIn size={14} />
          </button>
          <button type="button" className={styles.icon} onClick={onReset} aria-label="Reset view" title="Reset view">
            <RotateCcw size={14} />
          </button>
          <span className={styles.divider} />
        </>
      )}

      <button type="button" className={styles.action} onClick={copy} title="Copy diagram source">
        {copied ? <Check size={13} /> : <Copy size={13} />}
        {copied ? 'Copied' : 'Copy'}
      </button>
      {!arranging && onDownloadSvg && (
        <button type="button" className={styles.action} onClick={onDownloadSvg} title="Download as SVG">
          <Download size={13} />
          SVG
        </button>
      )}
      {canArrange && !arranging && (
        <button
          type="button"
          className={styles.action}
          onClick={onToggleArrange}
          title="Arrange nodes (drag to reposition)"
        >
          <Workflow size={13} />
          Arrange
        </button>
      )}

      <span className={styles.hint}>
        {arranging ? 'drag nodes · controls bottom-left' : 'scroll: zoom · drag: pan'}
      </span>
    </div>
  )
}
