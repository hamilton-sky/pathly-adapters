import { useEffect, useState } from 'react'

export interface CatalogItemData {
  name: string
  path?: string
  description?: string
  category?: string
}

export interface CatalogGroup {
  label: string
  type: 'agent' | 'fragment' | 'skill' | 'template'
  icon: 'brain' | 'diamond' | 'book-open' | 'layout-grid'
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

function toItem(r: ApiItem): CatalogItemData {
  return {
    name:        r.name,
    path:        r.path || undefined,
    description: r.description || undefined,
    category:    r.category || undefined,
  }
}

/**
 * Fetch the full catalog from the FSM server in one round-trip.
 * _pathlyRoot is kept for API compatibility but is no longer used —
 * the server knows where pathly_data lives.
 */
export function useCatalogData(_pathlyRoot?: string | null): CatalogGroup[] {
  const [groups, setGroups] = useState<CatalogGroup[]>([])

  useEffect(() => {
    fetch('http://localhost:8765/catalog/all')
      .then(r => r.json() as Promise<CatalogAllResponse>)
      .then(data => {
        const next: CatalogGroup[] = []
        if (data.agents?.length)
          next.push({ label: 'Agents',    type: 'agent',    icon: 'brain',       items: data.agents.map(toItem) })
        if (data.fragments?.length)
          next.push({ label: 'Fragments', type: 'fragment', icon: 'diamond',     items: data.fragments.map(toItem) })
        if (data.skills?.length)
          next.push({ label: 'Skills',    type: 'skill',    icon: 'book-open',   items: data.skills.map(toItem) })
        if (data.templates?.length)
          next.push({ label: 'Templates', type: 'template', icon: 'layout-grid', items: data.templates.map(toItem) })
        setGroups(next)
      })
      .catch(() => {})
  }, [])  // fetch once on mount — server rebuilds the index on every start

  return groups
}
