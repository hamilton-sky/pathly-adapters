import { useCallback, useEffect, useState } from 'react'
import { useStore } from '../store'
import { listDir, listDirs } from '../services/pathlyApi'
import type { PathlyItem, SectionState, TemplateSubdir } from '../types'
import type { Section } from '../components/sidebar/types'

const PATHLY_SECTIONS = [
  { label: 'Flows',     type: 'flow'     as const, dir: 'src/pathly_data/core/flows'     },
  { label: 'Skills',    type: 'skill'    as const, dir: 'src/pathly_data/core/skills'    },
  { label: 'Agents',    type: 'agent'    as const, dir: 'src/pathly_data/core/agents'    },
  { label: 'Templates', type: 'template' as const, dir: 'src/pathly_data/core/templates' },
]

const WORKSPACE_SECTIONS = [
  { label: 'Debugs',               type: 'debug'   as const, dir: 'pathly/debugs'               },
  { label: 'Explorations',         type: 'explore' as const, dir: 'pathly/explorations'         },
  { label: 'Lessons',              type: 'explore' as const, dir: 'pathly/lessons'              },
  { label: 'Pipeline-walkthrough', type: 'explore' as const, dir: 'pathly/pipeline-walkthrough' },
]

const USER_LIBRARY_SECTIONS = [
  { label: 'UserAgents',    type: 'agent'    as const, dir: 'agents'    },
  { label: 'UserSkills',    type: 'skill'    as const, dir: 'skills'    },
  { label: 'UserTemplates', type: 'template' as const, dir: 'templates' },
  { label: 'UserFlows',     type: 'flow'     as const, dir: 'flows'     },
]

const WORKSPACE_USER_SECTIONS = [
  { label: 'My Agents',    type: 'agent'    as const, dir: 'pathly/agents'    },
  { label: 'My Skills',    type: 'skill'    as const, dir: 'pathly/skills'    },
  { label: 'My Templates', type: 'template' as const, dir: 'pathly/templates' },
  { label: 'My Flows',     type: 'flow'     as const, dir: 'pathly/flows'     },
]

const INITIAL_SECTIONS: Record<string, SectionState> = {
  Flows:        { items: [], open: false },
  Skills:       { items: [], open: false },
  Agents:       { items: [], open: false },
  Templates:    { items: [], open: true  },
  Debugs:                 { items: [], open: false },
  Explorations:           { items: [], open: false },
  Lessons:                { items: [], open: false },
  'Pipeline-walkthrough': { items: [], open: false },
  UserAgents:    { items: [], open: false },
  UserSkills:    { items: [], open: false },
  UserTemplates: { items: [], open: false },
  UserFlows:     { items: [], open: false },
  'My Agents':    { items: [], open: false },
  'My Skills':    { items: [], open: false },
  'My Templates': { items: [], open: false },
  'My Flows':     { items: [], open: false },
}

async function loadSubdirAwareSection(
  dir: string,
  type: 'flow' | 'skill' | 'agent' | 'template' | 'debug' | 'explore',
): Promise<{ items: PathlyItem[]; subdirs: TemplateSubdir[] | null }> {
  if (type === 'template') {
    try {
      const subdirNames = await listDirs(dir)
      const subdirs: TemplateSubdir[] = []
      for (const subdirName of subdirNames) {
        const subdirPath = `${dir}/${subdirName}`
        let files: PathlyItem[] = []
        try {
          const fileNames = await listDir(subdirPath)
          files = fileNames
            .filter((f) => f !== '.gitkeep')
            .map((fname) => ({ name: fname, path: `${subdirPath}/${fname}`, type }))
        } catch { /* empty subdir */ }
        subdirs.push({ name: subdirName, open: false, files })
      }
      return { items: [], subdirs }
    } catch {
      return { items: [], subdirs: null }
    }
  }

  try {
    const names = await listDir(dir)
    try {
      const subdirNames = await listDirs(dir)
      const subdirSet = new Set(subdirNames)
      const fileNames = names.filter((n) => !subdirSet.has(n))
      const items: PathlyItem[] = fileNames.map((name) => ({
        name, path: `${dir}/${name}`, type,
      }))
      const subdirs: TemplateSubdir[] = []
      for (const subdirName of subdirNames) {
        const subdirPath = `${dir}/${subdirName}`
        let files: PathlyItem[] = []
        try {
          const subFiles = await listDir(subdirPath)
          files = subFiles
            .filter((f) => f !== '.gitkeep')
            .map((fname) => ({ name: fname, path: `${subdirPath}/${fname}`, type }))
        } catch { /* empty subdir */ }
        subdirs.push({ name: subdirName, open: false, files })
      }
      return { items, subdirs }
    } catch {
      const items: PathlyItem[] = names.map((name) => ({
        name, path: `${dir}/${name}`, type,
      }))
      return { items, subdirs: [] }
    }
  } catch {
    return { items: [], subdirs: null }
  }
}

const KNOWN_PATHLY_DIRS = new Set(['debugs', 'explorations', 'plans', 'agents', 'skills', 'templates', 'flows', 'lessons', 'pipeline-walkthrough'])

export function useProjectFiles(): {
  sections: Record<string, SectionState>
  setSections: React.Dispatch<React.SetStateAction<Record<string, SectionState>>>
  loadItems: () => Promise<void>
  customWorkspaceSections: Section[]
} {
  const { projectPath, pathlyRoot, pathlyUserHome } = useStore()
  const [sections, setSections] = useState<Record<string, SectionState>>(INITIAL_SECTIONS)
  const [customWorkspaceSections, setCustomWorkspaceSections] = useState<Section[]>([])

  // Section A (Flows/Skills/Agents/Templates) loads from the pathly installation,
  // not the open workspace project.
  const coreRoot = pathlyRoot

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
              files = fileNames
                .filter((f) => f !== '.gitkeep')
                .map((fname) => ({ name: fname, path: `${subdirPath}/${fname}`, type: section.type }))
            } catch { /* empty subdir */ }
            subdirs.push({ name: subdirName, open: false, files })
          }
          setSections((prev) => ({ ...prev, [section.label]: { ...prev[section.label], items: [], subdirs } }))
        } else {
          const names = await listDir(dir)
          let subdirs: TemplateSubdir[] = []
          try {
            const subdirNames = await listDirs(dir)
            const subdirSet = new Set(subdirNames)
            const fileNames = names.filter((n) => !subdirSet.has(n))
            const items: PathlyItem[] = fileNames.map((name) => ({
              name, path: `${dir}/${name}`, type: section.type,
            }))
            for (const subdirName of subdirNames) {
              const subdirPath = `${dir}/${subdirName}`
              let files: PathlyItem[] = []
              try {
                const subFiles = await listDir(subdirPath)
                files = subFiles
                  .filter((f) => f !== '.gitkeep')
                  .map((fname) => ({ name: fname, path: `${subdirPath}/${fname}`, type: section.type }))
              } catch { /* empty subdir */ }
              subdirs.push({ name: subdirName, open: false, files })
            }
            setSections((prev) => ({ ...prev, [section.label]: { ...prev[section.label], items, subdirs } }))
          } catch {
            const items: PathlyItem[] = names.map((name) => ({
              name, path: `${dir}/${name}`, type: section.type,
            }))
            setSections((prev) => ({ ...prev, [section.label]: { ...prev[section.label], items, subdirs } }))
          }
        }
      } catch {
        if (section.type === 'template') {
          setSections((prev) => ({ ...prev, [section.label]: { ...prev[section.label], items: [], subdirs: null } }))
        } else {
          setSections((prev) => ({ ...prev, [section.label]: { ...prev[section.label], items: [] } }))
        }
      }
    }

    // User library — global ~/.pathly sections
    if (pathlyUserHome) {
      for (const section of USER_LIBRARY_SECTIONS) {
        const dir = `${pathlyUserHome}/${section.dir}`
        const result = await loadSubdirAwareSection(dir, section.type)
        setSections((prev) => ({
          ...prev,
          [section.label]: { ...prev[section.label], items: result.items, subdirs: result.subdirs ?? undefined },
        }))
      }
    }

    if (!projectPath) return

    for (const section of WORKSPACE_SECTIONS) {
      const dir = `${projectPath}/${section.dir}`
      const result = await loadSubdirAwareSection(dir, section.type)
      setSections((prev) => ({
        ...prev,
        [section.label]: { ...prev[section.label], items: result.items, subdirs: result.subdirs ?? undefined },
      }))
    }

    // Discover any custom folders at pathly/ root (not in known dirs)
    try {
      const pathlyRootDirs = await listDirs(`${projectPath}/pathly`).catch(() => [] as string[])
      const customDirs = pathlyRootDirs.filter((d) => !KNOWN_PATHLY_DIRS.has(d))
      const discovered: Section[] = []
      for (const dirName of customDirs) {
        const label = dirName.charAt(0).toUpperCase() + dirName.slice(1)
        const dir = `pathly/${dirName}`
        discovered.push({ label, type: 'explore', dir })
        const result = await loadSubdirAwareSection(`${projectPath}/${dir}`, 'explore')
        setSections((prev) => ({
          ...prev,
          [label]: { open: prev[label]?.open ?? true, items: result.items, subdirs: result.subdirs ?? undefined },
        }))
      }
      setCustomWorkspaceSections(discovered)
    } catch { /* pathly/ root not found */ }

    // Workspace user sections — project-local authoring dirs
    for (const section of WORKSPACE_USER_SECTIONS) {
      const dir = `${projectPath}/${section.dir}`
      const result = await loadSubdirAwareSection(dir, section.type)
      setSections((prev) => ({
        ...prev,
        [section.label]: { ...prev[section.label], items: result.items, subdirs: result.subdirs ?? undefined },
      }))
    }
  }, [coreRoot, projectPath, pathlyUserHome])

  useEffect(() => {
    void loadItems()
    if (!projectPath) return
    const watchApi = window.pathly?.watch
    if (!watchApi) return
    const { watchWorkspace, onWorkspaceChanged } = watchApi
    if (!watchWorkspace || !onWorkspaceChanged) return
    void watchWorkspace(projectPath)
    return onWorkspaceChanged(() => { void loadItems() })
  }, [coreRoot, projectPath, pathlyUserHome, loadItems])

  return { sections, setSections, loadItems, customWorkspaceSections }
}
