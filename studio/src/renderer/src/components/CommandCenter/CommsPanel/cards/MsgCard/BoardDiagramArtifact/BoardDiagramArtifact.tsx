// Renders a diagram ARTIFACT on the comms board: a clamped DiagramRender preview that opens
// the full DiagramLightbox (zoom / pan / Arrange) on click — the same view as the editor
// gallery. Reuses the MarkdownEditor diagram components. Board diagrams don't persist Arrange
// layout (no sidecar), so the lightbox mounts without onSaveLayout.

import React, { useEffect, useState } from 'react'
import type { Message } from '../../../../types'
import type { DiagramEntry, DiagramStyle } from '../../../../../MarkdownEditor/diagramTypes'
import DiagramRender from '../../../../../MarkdownEditor/DiagramGalleryPanel/DiagramRender/DiagramRender'
import DiagramLightbox from '../../../../../MarkdownEditor/DiagramGalleryPanel/DiagramLightbox/DiagramLightbox'
import s from './BoardDiagramArtifact.module.css'

/** Style if this artifact message is a diagram, else null. mermaid/.mmd & plantuml/.puml by
 *  extension; ascii/.txt disambiguated by the "Diagram: … (ascii)" post text. */
export function diagramArtifactStyle(msg: { artifactPath?: string; text?: string }): DiagramStyle | null {
  const p = (msg.artifactPath ?? '').toLowerCase()
  if (p.endsWith('.mmd')) return 'mermaid'
  if (p.endsWith('.puml')) return 'plantuml'
  if (p.endsWith('.txt') && /^diagram:.*\(ascii\)\s*$/i.test(msg.text ?? '')) return 'ascii'
  return null
}

function titleFromText(text: string): string {
  const m = text.match(/^Diagram:\s*(.*?)\s*\([^)]*\)\s*$/i)
  return (m?.[1] || 'Diagram').trim()
}

interface Props {
  message: Message
  style: DiagramStyle
}

export default function BoardDiagramArtifact({ message, style }: Props) {
  const [content, setContent] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!message.artifactPath) return
    let active = true
    void window.pathly.fs.read(message.artifactPath).then((c) => {
      if (active) setContent(c ?? '')
    })
    return () => {
      active = false
    }
  }, [message.artifactPath])

  if (content == null) return <div className={s.loading}>Loading diagram…</div>

  const entry: DiagramEntry = {
    id: message.id,
    title: titleFromText(message.text),
    style,
    content,
    status: 'kept',
    engine: '',
    model: null,
    createdAt: message.ts ?? '',
  }

  return (
    <div className={s.wrap}>
      <button
        type="button"
        className={s.preview}
        onClick={() => setOpen(true)}
        aria-label={`View ${entry.title}`}
      >
        <DiagramRender entry={entry} mode="card" />
      </button>
      <div className={s.cap}>
        <span className={s.dot} data-style={style} />
        {entry.title} · {style}
      </div>
      {open && (
        <DiagramLightbox entry={entry} fileName={message.artifact ?? 'diagram'} onClose={() => setOpen(false)} />
      )}
    </div>
  )
}
