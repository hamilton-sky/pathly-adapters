import React from 'react'
import { Brain, Diamond, BookOpen, LayoutGrid, GitBranch, Sparkles, Scroll } from 'lucide-react'
import type { CatalogItemData, CatalogGroup } from './useCatalogData'

export function GroupIcon({ icon }: { icon: CatalogGroup['icon'] }) {
  if (icon === 'brain') return <Brain size={15} />
  if (icon === 'diamond') return <Diamond size={15} />
  if (icon === 'book-open') return <BookOpen size={15} />
  if (icon === 'git-branch') return <GitBranch size={15} />
  if (icon === 'sparkles') return <Sparkles size={15} />
  if (icon === 'scroll') return <Scroll size={15} />
  return <LayoutGrid size={15} />
}

export function leafName(item: CatalogItemData): string {
  const slash = item.name.lastIndexOf('/')
  return slash >= 0 ? item.name.slice(slash + 1) : item.name
}

export interface CatNode {
  items: CatalogItemData[]
  children: Record<string, CatalogItemData[]>
}

export function buildCategoryTree(
  groupItems: CatalogItemData[],
  groupType: string,
): Record<string, CatNode> {
  const tree: Record<string, CatNode> = {}
  for (const item of groupItems) {
    const raw = item.category || '_other'
    const slash = raw.indexOf('/')
    if (slash >= 0) {
      const parent = raw.slice(0, slash)
      const child = raw.slice(slash + 1)
      if (!tree[parent]) tree[parent] = { items: [], children: {} }
      if (!tree[parent].children[child]) tree[parent].children[child] = []
      tree[parent].children[child].push(item)
    } else {
      const key = raw === groupType ? '_other' : raw
      if (!tree[key]) tree[key] = { items: [], children: {} }
      tree[key].items.push(item)
    }
  }
  return tree
}
