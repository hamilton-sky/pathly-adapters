import { useEffect, useState } from 'react'
import { useStore } from '../../../store'
import { listAbilities } from '../../../services/abilities'
import { listUserPrompts } from '../../../services/promptLibrary'
import { BUILTIN_SYSTEM_ITEMS } from './builtinSystemPrompts'

export interface CatalogItemData {
  name: string
  path?: string
  description?: string
  category?: string
  itemType?: 'agent' | 'fragment' | 'skill' | 'template' | 'flow' | 'ability' | 'system'
  /** prompt_library row id (system-prompts) — backs delete/rename by id. */
  id?: string
  /** ability scope (project|global) — backs delete against the right store. */
  scope?: 'project' | 'global'
  /** App-shipped builtin (read-only): shown for reference, but not delete/rename/move-able. */
  readOnly?: boolean
}

export interface CatalogGroup {
  label: string
  type: 'agent' | 'fragment' | 'skill' | 'template' | 'flow' | 'ability' | 'system'
  icon: 'brain' | 'diamond' | 'book-open' | 'layout-grid' | 'git-branch' | 'sparkles' | 'scroll'
  items: CatalogItemData[]
}

interface ApiItem {
  name: string
  description: string
  category: string
  path: string
}

interface CatalogAllResponse {
  agents:    ApiItem[]
  fragments: ApiItem[]
  skills:    ApiItem[]
  templates: ApiItem[]
}

interface FlowListItem {
  name: string
  file_path: string
  updated_at: string
}

function toItem(r: ApiItem, itemType: CatalogItemData['itemType']): CatalogItemData {
  return {
    name:        r.name,
    path:        r.path || undefined,
    description: r.description || undefined,
    category:    r.category || undefined,
    itemType,
  }
}

function flowToItem(f: FlowListItem): CatalogItemData {
  return {
    name:     f.name,
    path:     f.file_path || undefined,
    category: 'flows',
  }
}

import { apiFetch } from '../../../lib/config'

/**
 * Fetch the full catalog from the FSM server in one round-trip.
 * _pathlyRoot is kept for API compatibility but is no longer used —
 * the server knows where pathly_data lives.
 * refreshKey can be incremented by the caller to trigger a re-fetch.
 */
export function useCatalogData(_pathlyRoot?: string | null, refreshKey?: number): CatalogGroup[] {
  const projectPath = useStore((st) => st.projectPath)
  const [groups, setGroups] = useState<CatalogGroup[]>([])

  useEffect(() => {
    Promise.all([
      apiFetch('/catalog/all').then(r => r.json() as Promise<CatalogAllResponse>),
      apiFetch('/flows').then(r => r.json() as Promise<FlowListItem[]>).catch(() => [] as FlowListItem[]),
      // Layer-3 abilities — MERGED project + global (project overrides global on the same id),
      // the same source the compose path + run-gate pickers read; category → subgroup, opens its .md.
      listAbilities(projectPath).catch(() => []),
      // System-prompts — the prompt_library presets, the SAME table the Sections 'System' tab
      // pulls; category → subgroup. Created in this Library (DB rows, so no open-in-editor).
      listUserPrompts({ kind: 'preset', projectRoot: projectPath }).catch(() => []),
    ]).then(([data, flows, abilities, sysPrompts]) => {
      const next: CatalogGroup[] = []
      if (flows?.length)
        next.push({ label: 'Flows',     type: 'flow',     icon: 'git-branch',  items: flows.map(flowToItem) })
      if (data.agents?.length)
        next.push({ label: 'Agents',    type: 'agent',    icon: 'brain',       items: data.agents.map(r => toItem(r, 'agent')) })
      if (data.fragments?.length)
        next.push({ label: 'Fragments', type: 'fragment', icon: 'diamond',     items: data.fragments.map(r => toItem(r, 'fragment')) })
      // The two USER-owned tables always render (even empty) so their "+ New" create surface is
      // reachable — otherwise you could never create the FIRST ability / system-prompt. (The
      // packaged groups above stay length-gated: they're never empty in a real install.)
      next.push({ label: 'Abilities', type: 'ability',  icon: 'sparkles',    items: (abilities ?? []).map(a => ({ name: a.name, path: a.path, description: a.label, category: a.category, itemType: 'ability' as const, scope: a.scope })) })
      // System = the app-shipped builtins (analyze/split/comment/diagram, read-only) + the user's
      // own DB rows — the same union the editor/Sections selections show, now visible in one place.
      next.push({ label: 'System',    type: 'system',   icon: 'scroll',      items: [
        ...BUILTIN_SYSTEM_ITEMS,
        ...(sysPrompts ?? []).map(p => ({ name: p.label || p.name, description: p.label, category: p.category, itemType: 'system' as const, id: p.id })),
      ] })
      if (data.skills?.length)
        next.push({ label: 'Skills',    type: 'skill',    icon: 'book-open',   items: data.skills.map(r => toItem(r, 'skill')) })
      if (data.templates?.length)
        next.push({ label: 'Templates', type: 'template', icon: 'layout-grid', items: data.templates.map(r => toItem(r, 'template')) })
      setGroups(next)
    }).catch(() => {})
  }, [refreshKey, projectPath])

  return groups
}
