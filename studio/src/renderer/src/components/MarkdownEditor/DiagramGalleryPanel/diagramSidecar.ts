// Pure I/O for the diagram sidecar. No React, no store — just disk.
//
// Ownership contract (mirrors the AI-Split/Analyze draft model):
//   READ   — useDiagramSidecar on mount / after a run completes
//   WRITE  — the AGENT appends on generate; the renderer only REMOVES
//   NEVER  — the renderer appends. The agent owns the append path so two
//            writers never race on the same file.
//
// Paths assume this file sits at:
//   src/components/MarkdownEditor/DiagramGalleryPanel/diagramSidecar.ts

import { readFile, writeFile, deleteFile } from '../../../services/pathlyApi'
import {
  type DiagramSidecar,
  type DiagramEntry,
  sidecarPathFor,
} from '../diagramTypes'

/** Narrowing guard so a malformed sidecar can never crash the panel. */
function isValidSidecar(value: unknown): value is DiagramSidecar {
  if (typeof value !== 'object' || value === null) return false
  const v = value as Record<string, unknown>
  return v.version === 1 && typeof v.source === 'string' && Array.isArray(v.diagrams)
}

/** Read + parse the sidecar for `filePath`. Returns null if missing or invalid. */
export async function readSidecar(filePath: string): Promise<DiagramSidecar | null> {
  const raw = await readFile(sidecarPathFor(filePath))
  if (raw == null || raw.trim() === '') return null
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!isValidSidecar(parsed)) return null
    // Drop any entry missing the required fields rather than rendering a broken card.
    parsed.diagrams = parsed.diagrams.filter(
      (d: DiagramEntry) => d && typeof d.id === 'string' && typeof d.content === 'string',
    )
    return parsed
  } catch {
    return null
  }
}

/**
 * Remove one diagram by id and persist the result.
 * Returns the updated sidecar, or null when the last entry was removed
 * (in which case the sidecar file itself is deleted).
 */
export async function removeDiagram(
  filePath: string,
  id: string,
): Promise<DiagramSidecar | null> {
  const sidecar = await readSidecar(filePath)
  if (!sidecar) return null

  const diagrams = sidecar.diagrams.filter((d) => d.id !== id)

  if (diagrams.length === 0) {
    await deleteFile(sidecarPathFor(filePath)).catch(() => {})
    return null
  }

  const next: DiagramSidecar = { ...sidecar, diagrams }
  await writeFile(sidecarPathFor(filePath), JSON.stringify(next, null, 2))
  return next
}

/**
 * Persist Arrange-mode node positions for one diagram (a UI-only field, not content).
 * Renderer read-modify-write, same shape as removeDiagram. No-op if the sidecar/entry
 * is gone — never throws into the caller.
 */
export async function updateDiagramLayout(
  filePath: string,
  id: string,
  layout: Record<string, { x: number; y: number }>,
): Promise<void> {
  const sidecar = await readSidecar(filePath)
  if (!sidecar) return
  const diagrams = sidecar.diagrams.map((d) => (d.id === id ? { ...d, layout } : d))
  await writeFile(sidecarPathFor(filePath), JSON.stringify({ ...sidecar, diagrams }, null, 2))
}
