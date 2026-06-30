// Renders one diagram by style. Mermaid → live SVG (MermaidView); ASCII → <pre>;
// PlantUML → source + opt-in server render (PlantUmlView). Never throws — a bad diagram
// degrades to a readable text block instead of crashing the card.
//
// Path assumes: src/components/MarkdownEditor/DiagramGalleryPanel/DiagramRender/DiagramRender.tsx

import React from 'react'
import type { DiagramEntry } from '../../diagramTypes'
import MermaidView from './MermaidView'
import PlantUmlView from './PlantUmlView'
import styles from './DiagramRender.module.css'

interface Props {
  entry: DiagramEntry
  /** 'card' clamps height for the gallery; 'full' is unbounded for the lightbox. */
  mode: 'card' | 'full'
}

export default function DiagramRender({ entry, mode }: Props) {
  const cls = mode === 'card' ? styles.card : styles.full

  if (entry.style === 'mermaid') {
    return (
      <div className={cls}>
        <MermaidView id={entry.id} content={entry.content} />
      </div>
    )
  }

  if (entry.style === 'ascii') {
    return (
      <div className={cls}>
        <pre className={styles.mono}>{entry.content}</pre>
      </div>
    )
  }

  // plantuml — source by default; opt-in render against a configurable server.
  return (
    <div className={cls}>
      <PlantUmlView content={entry.content} />
    </div>
  )
}
