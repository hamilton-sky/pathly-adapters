// abilities — the client seam to layer-3 ability FILES (/skills/abilities).
//
// An ability is a user-authored approach/domain pack stored as markdown:
//   <project>/pathly/abilities/<category>/<name>.md   project-scoped (git-trackable)
//   ~/.pathly/abilities/<category>/<name>.md          global (cross-project)
// Its id is "<category>/<name>". They are FILES (not prompt_library rows) so they're
// browsable in the Library, editable in the MD editor, ##-splittable, and git-trackable —
// read at compose time exactly like fragments. Every call fails soft.

import { apiFetch } from '../lib/config'

export interface Ability {
  /** "<category>/<name>" — the ability's stable id. */
  id: string
  category: string
  name: string
  label: string
  body: string
  scope: 'project' | 'global'
  /** Absolute path of the .md — open it in the MD editor. */
  path: string
}

/** List abilities (global + project merged; a project ability wins on a shared id). */
export async function listAbilities(projectRoot?: string): Promise<Ability[]> {
  try {
    const params = new URLSearchParams()
    if (projectRoot) params.set('project_root', projectRoot)
    const q = params.toString()
    const r = await apiFetch(`/skills/abilities${q ? `?${q}` : ''}`)
    if (!r.ok) return []
    const data = (await r.json()) as { abilities?: Ability[] }
    return Array.isArray(data.abilities) ? data.abilities : []
  } catch {
    return []
  }
}

export interface SaveAbility {
  category: string
  name: string
  body: string
  scope?: 'project' | 'global'
  projectRoot?: string
}

/** Create/overwrite an ability .md. Returns the stored row, or null on any failure. */
export async function saveAbility(a: SaveAbility): Promise<Ability | null> {
  try {
    const r = await apiFetch('/skills/abilities', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category: a.category,
        name: a.name,
        body: a.body,
        scope: a.scope ?? 'project',
        project_root: a.projectRoot ?? '',
      }),
    })
    if (!r.ok) return null
    const data = (await r.json()) as { ability?: Ability }
    return data.ability ?? null
  } catch {
    return null
  }
}

/** Remove an ability .md by its "<category>/<name>" id. */
export async function deleteAbility(
  id: string,
  opts: { scope?: 'project' | 'global'; projectRoot?: string } = {},
): Promise<boolean> {
  try {
    const params = new URLSearchParams({ scope: opts.scope ?? 'project' })
    if (opts.projectRoot) params.set('project_root', opts.projectRoot)
    const r = await apiFetch(`/skills/abilities/${id}?${params.toString()}`, {
      method: 'DELETE',
    })
    return r.ok
  } catch {
    return false
  }
}
