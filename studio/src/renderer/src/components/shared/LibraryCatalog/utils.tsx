import React from 'react'
import { Brain, Diamond, BookOpen, LayoutGrid, GitBranch, Layers, Scroll } from 'lucide-react'
import type { CatalogItemData, CatalogGroup } from './useCatalogData'

export function GroupIcon({ icon }: { icon: CatalogGroup['icon'] }) {
  if (icon === 'brain') return <Brain size={15} />
  if (icon === 'diamond') return <Diamond size={15} />
  if (icon === 'book-open') return <BookOpen size={15} />
  if (icon === 'git-branch') return <GitBranch size={15} />
  if (icon === 'layers') return <Layers size={15} />
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

// The user-owned tables have a FIXED, canonical category set — the same buckets the app
// CONSUMES them from (an 'analyze' system-prompt feeds the Analyze config; a 'build' ability
// feeds a build stage). So their subfolders are these categories, always shown (even empty) and
// never user-extendable — you add items INTO the set, you don't invent new folders.
export const FIXED_CATEGORIES: Record<string, string[]> = {
  ability: ['plan', 'build', 'review', 'test'],
  system: ['system', 'analyze', 'split', 'comment', 'diagram'],
}

export function buildCategoryTree(
  groupItems: CatalogItemData[],
  groupType: string,
  fixedCategories?: string[],
): Record<string, CatNode> {
  const tree: Record<string, CatNode> = {}
  // Seed the fixed categories so they render as subfolders even before any item lands in them.
  for (const cat of fixedCategories ?? []) tree[cat] = { items: [], children: {} }
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
