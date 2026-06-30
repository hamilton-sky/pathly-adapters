// Shared types for the Diagram feature.
// The sidecar file lives beside its source markdown as `<file>.diagrams.json`
// and is the single source of truth for a file's diagrams. The AGENT owns
// appends; the renderer only reads and removes (see diagramSidecar.ts).

export type DiagramStyle = 'mermaid' | 'ascii' | 'plantuml'
export type DiagramStatus = 'draft' | 'kept'

export interface DiagramEntry {
  /** Stable id, e.g. `dg_k2j9m`. */
  id: string
  title: string
  style: DiagramStyle
  /** Raw diagram source (Mermaid DSL, ASCII text, or PlantUML). */
  content: string
  status: DiagramStatus
  /** CLI engine that produced it, e.g. `claude`. */
  engine: string
  /** Seam for a future per-model picker — null today. */
  model: string | null
  /** ISO-8601 timestamp. */
  createdAt: string
}

export interface DiagramSidecar {
  version: 1
  source: string
  diagrams: DiagramEntry[]
}

export const SIDECAR_SUFFIX = '.diagrams.json'

/** Resolve the sidecar path for a given source file. */
export function sidecarPathFor(filePath: string): string {
  return filePath + SIDECAR_SUFFIX
}

/** Pipeline-state colour token per render style (matches tokens.css signal hues). */
export const STYLE_COLOR_VAR: Record<DiagramStyle, string> = {
  mermaid: 'var(--blue)',
  ascii: 'var(--yellow)',
  plantuml: 'var(--purple)',
}
