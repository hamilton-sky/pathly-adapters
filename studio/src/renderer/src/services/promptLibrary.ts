// promptLibrary — the client seam to the DB-backed prompt library (/skills/prompts).
//
// The library is the ONE store behind every prompt dropdown + the layer-3 ability packs.
// kind='preset'  → single-select alternatives (analyze/diagram/eval/system dropdowns)
// kind='ability' → additive, stackable modifiers (domain/approach packs).
// Every call fails soft (→ [] / null) so a user-added prompt is an enhancement layer,
// never a hard dependency of the action.

import { apiFetch } from '../lib/config'

export interface PromptLibraryRow {
  id: string
  kind: string
  category: string
  name: string
  label: string
  hint: string | null
  body: string
  skill_ref: string | null
  source: string
  sort_order: number
}

export interface PromptLibraryQuery {
  kind: 'preset' | 'ability'
  /** Omit to list every category of that kind (e.g. all abilities). */
  category?: string
  projectRoot?: string
}

/** List library prompts for a kind (+ optional category), global + project merged. `[]` on any error. */
export async function listUserPrompts(q: PromptLibraryQuery): Promise<PromptLibraryRow[]> {
  try {
    const params = new URLSearchParams({ kind: q.kind })
    if (q.category) params.set('category', q.category)
    if (q.projectRoot) params.set('project_root', q.projectRoot)
    const r = await apiFetch(`/skills/prompts?${params.toString()}`)
    if (!r.ok) return []
    const data = (await r.json()) as { prompts?: PromptLibraryRow[] }
    return Array.isArray(data.prompts) ? data.prompts : []
  } catch {
    return []
  }
}

export interface SaveUserPrompt {
  kind: 'preset' | 'ability'
  category: string
  name: string
  label?: string
  hint?: string
  body: string
  skillRef?: string
  projectRoot?: string
}

/** Create (or upsert on name-within-scope) a library prompt. Returns the stored row or null. */
export async function saveUserPrompt(p: SaveUserPrompt): Promise<PromptLibraryRow | null> {
  try {
    const r = await apiFetch('/skills/prompts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        kind: p.kind,
        category: p.category,
        name: p.name,
        label: p.label ?? p.name,
        hint: p.hint ?? '',
        body: p.body,
        skill_ref: p.skillRef ?? null,
        project_root: p.projectRoot ?? '',
      }),
    })
    if (!r.ok) return null
    const data = (await r.json()) as { prompt?: PromptLibraryRow }
    return data.prompt ?? null
  } catch {
    return null
  }
}

/** Delete a library prompt by id. */
export async function deleteUserPrompt(id: string, projectRoot?: string): Promise<boolean> {
  try {
    const params = new URLSearchParams()
    if (projectRoot) params.set('project_root', projectRoot)
    const q = params.toString()
    const r = await apiFetch(`/skills/prompts/${id}${q ? `?${q}` : ''}`, { method: 'DELETE' })
    return r.ok
  } catch {
    return false
  }
}

/** Patch a library prompt by id (only label/body here — the server ignores unknown keys). */
export async function updateUserPrompt(
  id: string,
  patch: { label?: string; body?: string; projectRoot?: string },
): Promise<boolean> {
  try {
    const r = await apiFetch(`/skills/prompts/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label: patch.label, body: patch.body, project_root: patch.projectRoot ?? '' }),
    })
    return r.ok
  } catch {
    return false
  }
}
