import { useState, useEffect } from 'react'

export interface CatalogItem {
  name: string  // display key (stem for agents, "dir/stem" for skills)
  path: string  // file path relative to core dir, no .md extension
}

export function useAgentCatalog(projectPath: string | null): CatalogItem[] {
  const [items, setItems] = useState<CatalogItem[]>([])

  useEffect(() => {
    if (!projectPath) return
    const base = `${projectPath}/src/pathly_data/core/agents`
    void (async () => {
      const catalog: CatalogItem[] = []
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
      setItems(catalog)
    })()
  }, [projectPath])

  return items
}

export function useSkillCatalog(projectPath: string | null): CatalogItem[] {
  const [items, setItems] = useState<CatalogItem[]>([])

  useEffect(() => {
    if (!projectPath) return
    const base = `${projectPath}/src/pathly_data/core/skills`
    void (async () => {
      const catalog: CatalogItem[] = []
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
      setItems(catalog)
    })()
  }, [projectPath])

  return items
}
