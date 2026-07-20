// promptLibrary — the client seam to the prompt store (/skills/prompts).
//
// The store is the ONE source behind every prompt dropdown.
// kind='preset'  → single-select alternatives (analyze/split/comment/diagram/system dropdowns).
//                  These are now FILES (pathly/prompts/<category>/<name>.md + ~/.pathly/prompts/),
//                  so a row carries a `path` (openable in the MD editor) + `scope`, and its
//                  `id` is "<category>/<name>". Same JSON shape as before otherwise.
// kind='ability' → legacy DB rows (real abilities live in services/abilities.ts as files).
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
  /** preset files only: 'project' | 'global' — which store the file lives in. */
  scope?: 'project' | 'global'
  /** preset files only: absolute path of the .md — open it in the MD editor. */
  path?: string
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
  /** preset files: which store to write ('project' | 'global'). Default 'project'. */
  scope?: 'project' | 'global'
  projectRoot?: string
}

/** Create/overwrite a prompt (a preset writes a file). Returns the stored row or null. */
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
        scope: p.scope ?? 'project',
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

/** Delete a system-prompt FILE by its "<category>/<name>" id (+ scope). */
export async function deleteUserPrompt(
  id: string,
  opts: { scope?: 'project' | 'global'; projectRoot?: string } = {},
): Promise<boolean> {
  try {
    const params = new URLSearchParams({ scope: opts.scope ?? 'project' })
    if (opts.projectRoot) params.set('project_root', opts.projectRoot)
    // `id` is "<category>/<name>" — its slash IS the path separator, so it is NOT encoded.
    const r = await apiFetch(`/skills/prompts/${id}?${params.toString()}`, { method: 'DELETE' })
    return r.ok
  } catch {
    return false
  }
}
