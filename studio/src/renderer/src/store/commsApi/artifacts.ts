// The comms_artifacts side-table: the files a board produced, plus the per-artifact AI
// summary settings (target engine, depth style, free-text note) and their app-wide defaults.

import { apiFetch } from '../../lib/config'

/** A stored artifact row (one per file produced on a board, many-per-task). */
export interface ArtifactRow {
  id: string
  message_id: string
  path: string
  type: string | null
  title: string | null
  summary: string | null
  token_count: number | null
  created_at: string
  created_by: string | null
  last_edit_at: string | null
  last_edit_by: string | null
  version: number | null
  supersedes: string | null
  /** JSON-encoded AiSelection {type,id} — the saved per-artifact summary target. */
  summary_selection?: string | null
  /** Per-artifact summary DEPTH style; null → the default ('topic-map'). */
  summary_style?: SummaryStyle | null
  /** Per-artifact free-text "special request" appended to the summary prompt; null → none. */
  summary_note?: string | null
}

/** Summary DEPTH style — selects which development/summarize* skill the client composes. */
export type SummaryStyle = 'gist' | 'topic-map' | 'detailed'
export const SUMMARY_STYLE_DEFAULT: SummaryStyle = 'topic-map'

/** Fetch the artifacts linked to a message. Returns [] on any failure. */
export async function fetchArtifacts(messageId: string): Promise<ArtifactRow[]> {
  try {
    const r = await apiFetch(`/comms/artifacts?message_id=${encodeURIComponent(messageId)}`)
    const data = (await r.json()) as { ok?: boolean; artifacts?: ArtifactRow[] }
    return Array.isArray(data.artifacts) ? data.artifacts : []
  } catch {
    return []
  }
}

// ── unified-ai-routing (Conv 3): client-side summary + per-artifact target ──

/** AiSelection mirror — kept structural so commsApi doesn't import the service layer. */
export interface AiSelectionDto {
  type: 'model' | 'engine'
  id: string
}

/**
 * Write a CLIENT-computed summary back to comms_artifacts (the renderer runs
 * aiRouter, then posts the text here — the server runs no inference). Pass
 * `selection` to also persist the target that produced it. Returns true on 2xx.
 */
export async function apiSetArtifactSummary(
  artifactId: string,
  summary: string,
  selection?: AiSelectionDto,
): Promise<boolean> {
  try {
    const r = await apiFetch(`/comms/artifacts/${encodeURIComponent(artifactId)}/summary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ summary, ...(selection ? { selection } : {}) }),
    })
    return r.ok
  } catch {
    return false
  }
}

/** Persist a per-artifact AI target (so Re-summarize reuses it). Returns true on 2xx. */
export async function apiSetArtifactSelection(
  artifactId: string,
  selection: AiSelectionDto,
): Promise<boolean> {
  try {
    const r = await apiFetch(`/comms/artifacts/${encodeURIComponent(artifactId)}/selection`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ selection }),
    })
    return r.ok
  } catch {
    return false
  }
}

/** Persist a per-artifact summary DEPTH style (so Re-summarize reuses it). Returns true on 2xx. */
export async function apiSetArtifactStyle(
  artifactId: string,
  style: SummaryStyle,
): Promise<boolean> {
  try {
    const r = await apiFetch(`/comms/artifacts/${encodeURIComponent(artifactId)}/style`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ style }),
    })
    return r.ok
  } catch {
    return false
  }
}

/** Persist a per-artifact free-text "special request" (appended to the summary prompt). */
export async function apiSetArtifactNote(
  artifactId: string,
  note: string,
): Promise<boolean> {
  try {
    const r = await apiFetch(`/comms/artifacts/${encodeURIComponent(artifactId)}/note`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note }),
    })
    return r.ok
  } catch {
    return false
  }
}

/** Fetch the app-default summary AiSelection, or null when unset / on error. */
export async function apiGetDefaultSelection(): Promise<AiSelectionDto | null> {
  try {
    const r = await apiFetch('/comms/default-selection')
    if (!r.ok) return null
    const json = (await r.json()) as { selection?: AiSelectionDto | null }
    return json.selection ?? null
  } catch {
    return null
  }
}

/** Persist the app-default summary AiSelection. Returns true on 2xx. */
export async function apiSetDefaultSelection(selection: AiSelectionDto): Promise<boolean> {
  try {
    const r = await apiFetch('/comms/default-selection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ selection }),
    })
    return r.ok
  } catch {
    return false
  }
}

/** Fetch the app-default summary depth style, or null when unset / on error. */
export async function apiGetDefaultStyle(): Promise<SummaryStyle | null> {
  try {
    const r = await apiFetch('/comms/default-style')
    if (!r.ok) return null
    const json = (await r.json()) as { style?: SummaryStyle | null }
    return json.style ?? null
  } catch {
    return null
  }
}

/** Persist the app-default summary depth style. Returns true on 2xx. */
export async function apiSetDefaultStyle(style: SummaryStyle): Promise<boolean> {
  try {
    const r = await apiFetch('/comms/default-style', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ style }),
    })
    return r.ok
  } catch {
    return false
  }
}
