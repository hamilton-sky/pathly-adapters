// Footer action bar for the diagram lightbox: zoom controls, reset, copy-source, and
// (mermaid only) SVG export. Self-contained — owns its transient "copied" feedback.
//
// Path assumes:
//   src/components/MarkdownEditor/DiagramGalleryPanel/DiagramLightbox/DiagramLightboxToolbar/DiagramLightboxToolbar.tsx

import React, { useState } from 'react'
import { ZoomIn, ZoomOut, RotateCcw, Copy, Check, Download } from 'lucide-react'
import styles from './DiagramLightboxToolbar.module.css'

interface Props {
  zoom: number
  onZoomIn: () => void
  onZoomOut: () => void
  onReset: () => void
  onCopySource: () => void
  /** Null for non-mermaid styles (no rendered SVG to export). */
  onDownloadSvg: (() => void) | null
}

export default function DiagramLightboxToolbar({
  zoom,
  onZoomIn,
  onZoomOut,
  onReset,
  onCopySource,
  onDownloadSvg,
}: Props) {
  const [copied, setCopied] = useState(false)

  const copy = () => {
    onCopySource()
    setCopied(true)
    setTimeout(() => setCopied(false), 1200)
  }

  return (
    <div className={styles.bar}>
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

      <button type="button" className={styles.action} onClick={copy} title="Copy diagram source">
        {copied ? <Check size={13} /> : <Copy size={13} />}
        {copied ? 'Copied' : 'Copy'}
      </button>
      {onDownloadSvg && (
        <button type="button" className={styles.action} onClick={onDownloadSvg} title="Download as SVG">
          <Download size={13} />
          SVG
        </button>
      )}

      <span className={styles.hint}>scroll: zoom · drag: pan</span>
    </div>
  )
}
