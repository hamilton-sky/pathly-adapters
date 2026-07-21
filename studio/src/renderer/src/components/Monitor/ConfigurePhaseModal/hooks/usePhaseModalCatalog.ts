import { useState, useEffect } from 'react'
import { PATHLY_API_BASE } from '../../../../lib/config'

export interface CatalogItem {
  name: string  // display key (stem for agents, "dir/stem" for skills)
  path: string  // file path relative to core dir, no .md extension
}

// The FSM server's installed-core registry — the REAL agent/skill set, available for ANY
// project. The per-project FS read below only finds `core/` in the Pathly dev repo, so a user
// project would otherwise show a tiny hardcoded fallback. This also surfaces user-created
// agents/skills once they land in the installed core.
//
// Cached per kind so re-opening the Run modal (or re-mounting the form) doesn't re-fetch and
// flicker the dropdowns. Only a NON-empty result is cached — a 404 before the server picks up
// the new endpoint must not latch an empty list.
const _registryCache: Partial<Record<'agents' | 'skills', CatalogItem[]>> = {}

async function fetchRegistry(kind: 'agents' | 'skills'): Promise<CatalogItem[]> {
  const cached = _registryCache[kind]
  if (cached) return cached
  try {
    const r = await fetch(`${PATHLY_API_BASE}/registry/${kind}`)
    if (!r.ok) return []
    const data = await r.json()
    const items = Array.isArray(data) ? (data as CatalogItem[]) : []
    if (items.length) _registryCache[kind] = items
    return items
  } catch {
    return []
  }
}

export function useAgentCatalog(projectPath: string | null): CatalogItem[] {
  const [items, setItems] = useState<CatalogItem[]>([])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      // 1. The open project's own core dir (Pathly dev repo — reflects uncommitted edits).
      const catalog: CatalogItem[] = []
      if (projectPath) {
        const base = `${projectPath}/src/pathly_data/core/agents`
        const rootFiles = await window.pathly.fs.list(base).catch(() => [] as string[])
        for (const f of rootFiles) {
          if (f.endsWith('.md') && !f.startsWith('README')) {
            const stem = f.slice(0, -3)
            catalog.push({ name: stem, path: stem })
          }
        }
        const dirs = await window.pathly.fs.listDirs(base).catch(() => [] as string[])
        for (const dir of dirs) {
          const files = await window.pathly.fs.list(`${base}/${dir}`).catch(() => [] as string[])
          for (const f of files) {
            if (f.endsWith('.md')) {
              const stem = f.slice(0, -3)
              catalog.push({ name: stem, path: `${dir}/${stem}` })
            }
          }
        }
      }
      // 2. Fall back to the FSM server registry — works for any project.
      const resolved = catalog.length ? catalog : await fetchRegistry('agents')
      if (!cancelled) setItems(resolved)
    })()
    return () => {
      cancelled = true
    }
  }, [projectPath])

  return items
}

export function useSkillCatalog(projectPath: string | null): CatalogItem[] {
  const [items, setItems] = useState<CatalogItem[]>([])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      const catalog: CatalogItem[] = []
      if (projectPath) {
        const base = `${projectPath}/src/pathly_data/core/skills`
        const dirs = await window.pathly.fs.listDirs(base).catch(() => [] as string[])
        for (const dir of dirs) {
          if (dir === 'fragments') continue
          const files = await window.pathly.fs.list(`${base}/${dir}`).catch(() => [] as string[])
          for (const f of files) {
            if (f.endsWith('.md')) {
              const stem = f.slice(0, -3)
              catalog.push({ name: `${dir}/${stem}`, path: `${dir}/${stem}` })
            }
          }
        }
      }
      const resolved = catalog.length ? catalog : await fetchRegistry('skills')
      if (!cancelled) setItems(resolved)
    })()
    return () => {
      cancelled = true
    }
  }, [projectPath])

  return items
}
