// skillComposition — the client seam for the Skill Composition panel.
//
// Reads the merged (packaged composition.yaml + per-project DB override) fragment stack
// for every skill, and writes/deletes the per-project override via the same routes the
// skill notebook editor uses (PUT /skills/export, POST /skills/preview). This NEVER
// touches composition.yaml — every write lands in the skill_composition DB table.

import { apiFetch } from '../lib/config'

export interface SkillCompositionEntry {
  fragments: string[]
  source: 'manifest' | 'override'
}

export interface SkillCompositionCatalog {
  skills: Record<string, SkillCompositionEntry>
  all_fragments: string[]
}

export interface ComposedSection {
  heading: string
  content: string
  origin: string
}

/** Fetch every manifest skill's effective fragment list + the full fragment catalog. */
export async function fetchSkillComposition(projectRoot: string): Promise<SkillCompositionCatalog | null> {
  try {
    const params = new URLSearchParams()
    if (projectRoot) params.set('project_root', projectRoot)
    const qs = params.toString()
    const r = await apiFetch(`/skills/composition${qs ? `?${qs}` : ''}`)
    if (!r.ok) return null
    const data = (await r.json()) as SkillCompositionCatalog
    return data && typeof data.skills === 'object' ? data : null
  } catch {
    return null
  }
}

/** Persist a skill's fragment order as a per-project override (debounce the caller). */
export async function saveSkillCompositionOverride(
  skill: string,
  fragmentOrder: string[],
  projectRoot: string,
): Promise<boolean> {
  try {
    const r = await apiFetch('/skills/export', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skill, fragment_order: fragmentOrder, project_root: projectRoot }),
    })
    return r.ok
  } catch {
    return false
  }
}

/** Delete a skill's per-project override — reverts it to the packaged default. */
export async function resetSkillComposition(skill: string, projectRoot: string): Promise<boolean> {
  try {
    const r = await apiFetch('/skills/composition', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skill, project_root: projectRoot }),
    })
    return r.ok
  } catch {
    return false
  }
}

/** Live-preview `skill` composed with an explicit fragment list (not necessarily saved yet). */
export async function previewComposedSkill(
  skill: string,
  fragmentNames: string[],
  projectRoot: string,
): Promise<{ sections: ComposedSection[]; tokens: number } | null> {
  try {
    const r = await apiFetch('/skills/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        skill,
        cells: fragmentNames.map((name) => ({ type: 'fragment', fragmentName: name })),
        body_cells: [],
        feature_path: '',
        project_root: projectRoot,
      }),
    })
    if (!r.ok) return null
    const data = (await r.json()) as { sections?: ComposedSection[]; tokens?: number }
    return { sections: data.sections ?? [], tokens: data.tokens ?? 0 }
  } catch {
    return null
  }
}
