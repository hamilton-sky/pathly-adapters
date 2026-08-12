// Shared types for the Diagram feature.
// The sidecar file lives beside its source markdown as `<file>.diagrams.json`
// and is the single source of truth for a file's diagrams. The AGENT owns
// appends; the renderer only reads and removes (see diagramSidecar.ts).

export type DiagramStyle = 'mermaid' | 'ascii' | 'plantuml'
type DiagramStatus = 'draft' | 'kept'

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
  /** Saved React Flow node positions from Arrange mode (node id -> x/y). Optional. */
  layout?: Record<string, { x: number; y: number }>
  /** Set when the user posted this diagram to the comms board (renderer action). */
  board?: { id: string; at: string }
}

export interface DiagramSidecar {
  version: 1
  source: string
  diagrams: DiagramEntry[]
}

const SIDECAR_SUFFIX = '.diagrams.json'

/** Resolve the sidecar path for a given source file. */
export function sidecarPathFor(filePath: string): string {
  return filePath + SIDECAR_SUFFIX
}
