import { useCallback, useEffect, useState } from 'react'
import { useStore } from '../store'
import { listDir, listDirs } from '../services/pathlyApi'
import type { PathlyItem, SectionState, TemplateSubdir } from '../types'

const PATHLY_SECTIONS = [
  { label: 'Flows',     type: 'flow'     as const, dir: 'src/pathly_data/core/flows'     },
  { label: 'Skills',    type: 'skill'    as const, dir: 'src/pathly_data/core/skills'    },
  { label: 'Agents',    type: 'agent'    as const, dir: 'src/pathly_data/core/agents'    },
  { label: 'Templates', type: 'template' as const, dir: 'src/pathly_data/core/templates' },
]

const WORKSPACE_SECTIONS = [
  { label: 'Debugs',       type: 'debug'   as const, dir: 'pathly/debugs'       },
  { label: 'Explorations', type: 'explore' as const, dir: 'pathly/explorations' },
]

const INITIAL_SECTIONS: Record<string, SectionState> = {
  Flows:        { items: [], open: false },
  Skills:       { items: [], open: false },
  Agents:       { items: [], open: false },
  Templates:    { items: [], open: true  },
  Debugs:       { items: [], open: false },
  Explorations: { items: [], open: false },
}

export function useProjectFiles(): {
  sections: Record<string, SectionState>
  setSections: React.Dispatch<React.SetStateAction<Record<string, SectionState>>>
  loadItems: () => Promise<void>
} {
  const { projectPath, pathlyRoot } = useStore()
  const [sections, setSections] = useState<Record<string, SectionState>>(INITIAL_SECTIONS)

  // Section A (Flows/Skills/Agents/Templates) loads from the pathly installation,
  // not the open workspace project.
  const coreRoot = pathlyRoot || projectPath

  const loadItems = useCallback(async (): Promise<void> => {
    for (const section of PATHLY_SECTIONS) {
      if (!coreRoot) {
        if (section.type === 'template') {
          setSections((prev) => ({ ...prev, [section.label]: { ...prev[section.label], items: [], subdirs: [] } }))
        } else {
          setSections((prev) => ({ ...prev, [section.label]: { ...prev[section.label], items: [] } }))
        }
        continue
      }
      try {
        const dir = `${coreRoot}/${section.dir}`
        if (section.type === 'template') {
          const subdirNames = await listDirs(dir)
          const subdirs: TemplateSubdir[] = []
          for (const subdirName of subdirNames) {
            const subdirPath = `${dir}/${subdirName}`
            let files: PathlyItem[] = []
            try {
              const fileNames = await listDir(subdirPath)
              files = fileNames.map((fname) => ({ name: fname, path: `${subdirPath}/${fname}`, type: section.type }))
            } catch { /* empty subdir */ }
            subdirs.push({ name: subdirName, open: false, files })
          }
          setSections((prev) => ({ ...prev, [section.label]: { ...prev[section.label], items: [], subdirs } }))
        } else {
          const names = await listDir(dir)
          const items: PathlyItem[] = names.map((name) => ({
            name, path: `${dir}/${name}`, type: section.type,
          }))
          setSections((prev) => ({ ...prev, [section.label]: { ...prev[section.label], items } }))
        }
      } catch {
        if (section.type === 'template') {
          setSections((prev) => ({ ...prev, [section.label]: { ...prev[section.label], items: [], subdirs: null } }))
        } else {
          setSections((prev) => ({ ...prev, [section.label]: { ...prev[section.label], items: [] } }))
        }
      }
    }

    if (!projectPath) return

    for (const section of WORKSPACE_SECTIONS) {
      try {
        const dir = `${projectPath}/${section.dir}`
        const subdirNames = await listDirs(dir)
        const subdirs: TemplateSubdir[] = []
        for (const subdirName of subdirNames) {
          const subdirPath = `${dir}/${subdirName}`
          let files: PathlyItem[] = []
          try {
            const fileNames = await listDir(subdirPath)
            files = fileNames.map((fname) => ({ name: fname, path: `${subdirPath}/${fname}`, type: section.type }))
          } catch { /* empty subdir */ }
          subdirs.push({ name: subdirName, open: false, files })
        }
        setSections((prev) => ({ ...prev, [section.label]: { ...prev[section.label], items: [], subdirs } }))
      } catch {
        setSections((prev) => ({ ...prev, [section.label]: { ...prev[section.label], items: [], subdirs: null } }))
      }
    }
  }, [coreRoot, projectPath])

  useEffect(() => {
    void loadItems()
  }, [coreRoot, projectPath, loadItems])

  return { sections, setSections, loadItems }
}
