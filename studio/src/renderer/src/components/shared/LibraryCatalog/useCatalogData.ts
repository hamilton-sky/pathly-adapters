import { useEffect, useState } from 'react'

export interface CatalogItemData {
  name: string
  path?: string
  description?: string
  category?: string
  itemType?: 'agent' | 'fragment' | 'skill' | 'template' | 'flow'
}

export interface CatalogGroup {
  label: string
  type: 'agent' | 'fragment' | 'skill' | 'template' | 'flow'
  icon: 'brain' | 'diamond' | 'book-open' | 'layout-grid' | 'git-branch'
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
  const [groups, setGroups] = useState<CatalogGroup[]>([])

  useEffect(() => {
    Promise.all([
      apiFetch('/catalog/all').then(r => r.json() as Promise<CatalogAllResponse>),
      apiFetch('/flows').then(r => r.json() as Promise<FlowListItem[]>).catch(() => [] as FlowListItem[]),
    ]).then(([data, flows]) => {
      const next: CatalogGroup[] = []
      if (flows?.length)
        next.push({ label: 'Flows',     type: 'flow',     icon: 'git-branch',  items: flows.map(flowToItem) })
      if (data.agents?.length)
        next.push({ label: 'Agents',    type: 'agent',    icon: 'brain',       items: data.agents.map(r => toItem(r, 'agent')) })
      if (data.fragments?.length)
        next.push({ label: 'Fragments', type: 'fragment', icon: 'diamond',     items: data.fragments.map(r => toItem(r, 'fragment')) })
      if (data.skills?.length)
        next.push({ label: 'Skills',    type: 'skill',    icon: 'book-open',   items: data.skills.map(r => toItem(r, 'skill')) })
      if (data.templates?.length)
        next.push({ label: 'Templates', type: 'template', icon: 'layout-grid', items: data.templates.map(r => toItem(r, 'template')) })
      setGroups(next)
    }).catch(() => {})
  }, [refreshKey])

  return groups
}
