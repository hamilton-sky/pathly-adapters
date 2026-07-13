// Pure I/O for the analysis sidecar. No React, no store — just disk.
//
// Ownership contract (mirrors the Diagram sidecar model):
//   READ    — useAnalysisSidecar on mount / after a run completes
//   WRITE   — the AGENT appends on analyze; the renderer only REMOVES / marks-on-board
//   MIGRATE — the renderer folds a pre-gallery `<file>.analysis` into the array once
//   NEVER   — the renderer appends a report. The agent owns the append path so two
//             writers never race on the same file.
//
// Paths assume this file sits at:
//   src/components/MarkdownEditor/AnalysisGalleryPanel/analysisSidecar.ts

import { readFile, writeFile, deleteFile } from '../../../services/pathlyApi'
import {
  type AnalysisSidecar,
  type AnalysisEntry,
  analysisSidecarPathFor,
  legacyAnalysisPathFor,
} from '../analysisTypes'

/** Narrowing guard so a malformed sidecar can never crash the panel. */
function isValidSidecar(value: unknown): value is AnalysisSidecar {
  if (typeof value !== 'object' || value === null) return false
  const v = value as Record<string, unknown>
  return v.version === 1 && typeof v.source === 'string' && Array.isArray(v.analyses)
}

/** Read + parse the sidecar for `filePath`. Returns null if missing or invalid. */
export async function readSidecar(filePath: string): Promise<AnalysisSidecar | null> {
  const raw = await readFile(analysisSidecarPathFor(filePath))
  if (raw == null || raw.trim() === '') return null
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!isValidSidecar(parsed)) return null
    // Drop any entry missing the required fields rather than rendering a broken card.
    parsed.analyses = parsed.analyses.filter(
      (a: AnalysisEntry) => a && typeof a.id === 'string' && typeof a.content === 'string',
    )
    return parsed
  } catch {
    return null
  }
}

/**
 * Remove one report by id and persist the result.
 * Returns the updated sidecar, or null when the last entry was removed
 * (in which case the sidecar file itself is deleted).
 */
export async function removeAnalysis(
  filePath: string,
  id: string,
): Promise<AnalysisSidecar | null> {
  const sidecar = await readSidecar(filePath)
  if (!sidecar) return null

  const analyses = sidecar.analyses.filter((a) => a.id !== id)

  if (analyses.length === 0) {
    await deleteFile(analysisSidecarPathFor(filePath)).catch(() => {})
    return null
  }

  const next: AnalysisSidecar = { ...sidecar, analyses }
  await writeFile(analysisSidecarPathFor(filePath), JSON.stringify(next, null, 2))
  return next
}

/** Record that a report was posted to the board (renderer read-modify-write). */
export async function markAnalysisOnBoard(
  filePath: string,
  id: string,
  board: { id: string; at: string },
): Promise<void> {
  const sidecar = await readSidecar(filePath)
  if (!sidecar) return
  const analyses = sidecar.analyses.map((a) => (a.id === id ? { ...a, board } : a))
  await writeFile(analysisSidecarPathFor(filePath), JSON.stringify({ ...sidecar, analyses }, null, 2))
}

/**
 * One-time fold of a pre-gallery `<file>.analysis` (single markdown report) into the
 * array sidecar, then delete the legacy file. No-op when there is no legacy file or a
 * sidecar already exists (so it never clobbers real gallery data). Best-effort — any
 * failure leaves both files untouched and is swallowed. Returns true if it migrated.
 */
export async function migrateLegacyAnalysis(filePath: string): Promise<boolean> {
  try {
    // Never overwrite an existing gallery.
    if (await readSidecar(filePath)) return false
    const legacyPath = legacyAnalysisPathFor(filePath)
    const legacy = await readFile(legacyPath)
    if (legacy == null || legacy.trim() === '') return false

    const entry: AnalysisEntry = {
      id: 'an_' + Math.abs(hashString(legacy)).toString(36).slice(0, 5).padEnd(5, '0'),
      lens: 'legacy',
      title: 'Analysis report',
      content: legacy,
      engine: 'unknown',
      model: null,
      createdAt: new Date().toISOString(),
    }
    const sidecar: AnalysisSidecar = { version: 1, source: filePath.replace(/\\/g, '/'), analyses: [entry] }
    await writeFile(analysisSidecarPathFor(filePath), JSON.stringify(sidecar, null, 2))
    await deleteFile(legacyPath).catch(() => {})
    return true
  } catch {
    return false
  }
}

/** Deterministic id seed for the migrated entry (avoids Math.random for a stable id). */
function hashString(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = (h << 5) - h + s.charCodeAt(i)
    h |= 0
  }
  return h
}
