// Shared types for the multi-Analysis feature.
// The sidecar file lives beside its source markdown as `<file>.analyses.json`
// and is the single source of truth for a file's analysis reports. The AGENT owns
// appends; the renderer only reads and removes (see AnalysisGalleryPanel/analysisSidecar.ts).
//
// Mirrors diagramTypes.ts — the two editor "gallery" features share the same
// append-array-sidecar shape so their panels are structurally interchangeable.

/** Lens that produced a report. Free-form on disk (agent-stamped); these are the built-ins. */
export type AnalysisLens = 'full' | 'clarity' | 'gaps' | 'redundancy' | 'legacy'

export interface AnalysisEntry {
  /** Stable id, e.g. `an_k2j9m`. */
  id: string
  /** Lens key that produced this report (e.g. `clarity`). */
  lens: string
  /** Human title, e.g. `Clarity audit`. */
  title: string
  /** The full markdown report body. */
  content: string
  /** CLI engine that produced it, e.g. `claude`. */
  engine: string
  /** Seam for a future per-model picker — null today. */
  model: string | null
  /** ISO-8601 timestamp. */
  createdAt: string
  /** Set when the user posted this report to the comms board (renderer action). */
  board?: { id: string; at: string }
}

export interface AnalysisSidecar {
  version: 1
  source: string
  analyses: AnalysisEntry[]
}

export const ANALYSIS_SIDECAR_SUFFIX = '.analyses.json'
/** The pre-gallery single-report file — migrated into the sidecar on file open. */
export const LEGACY_ANALYSIS_SUFFIX = '.analysis'

/** Resolve the sidecar path for a given source file. */
export function analysisSidecarPathFor(filePath: string): string {
  return filePath + ANALYSIS_SIDECAR_SUFFIX
}

/** Resolve the legacy single-report path for a given source file. */
export function legacyAnalysisPathFor(filePath: string): string {
  return filePath + LEGACY_ANALYSIS_SUFFIX
}
