import { useCallback, useEffect, useState } from 'react'
import { useStore } from '../store'
import { listDir, listDirs, readFile } from '../services/pathlyApi'
import type { PathlyItem } from '../types'
import { parseProgressMd } from './usePlanConversations'

export interface PlanSubdir {
  name: string
  files: PathlyItem[]
  open: boolean
}

export interface PlanFolder {
  name: string
  path: string
  files: PathlyItem[]
  subdirs: PlanSubdir[]
  convTotal: number
  convDone: number
  open: boolean
}

export function usePlanFiles(): {
  planFolders: PlanFolder[]
  setPlanFolders: React.Dispatch<React.SetStateAction<PlanFolder[]>>
  loadPlanFiles: () => Promise<void>
} {
  const { projectPath } = useStore()
  const [planFolders, setPlanFolders] = useState<PlanFolder[]>([])

  const loadPlanFiles = useCallback(async (): Promise<void> => {
    if (!projectPath) { setPlanFolders([]); return }

    // Read a feature's plan files + subdirs from wherever its content lives. In the
    // feature-centric layout that is pathly/features/<name>/ directly; legacy features
    // keep their files in pathly/features/<name>/.
    async function scanContent(name: string, contentDir: string): Promise<PlanFolder> {
      let files: PathlyItem[] = []
      try {
        const fileNames = await listDir(contentDir)
        files = fileNames.map((fname) => ({ name: fname, path: `${contentDir}/${fname}`, type: 'plan' as const }))
      } catch { /* empty folder */ }
      const subdirs: PlanSubdir[] = []
      try {
        const subdirNames = await listDirs(contentDir)
        for (const sdName of subdirNames) {
          const sdPath = `${contentDir}/${sdName}`
          let sdFiles: PathlyItem[] = []
          try {
            const sdFileNames = await listDir(sdPath)
            sdFiles = sdFileNames.map((fname) => ({ name: fname, path: `${sdPath}/${fname}`, type: 'plan' as const }))
          } catch { /* empty subdir */ }
          subdirs.push({ name: sdName, files: sdFiles, open: false })
        }
      } catch { /* no subdirs */ }
      let convTotal = 0
      let convDone = 0
      try {
        const md = await readFile(`${contentDir}/PROGRESS.md`)
        if (md) {
          const convs = parseProgressMd(md)
          convTotal = convs.length
          convDone = convs.filter((c) => c.status === 'DONE').length
        }
      } catch { /* no PROGRESS.md */ }
      return { name, path: contentDir, files, subdirs, convTotal, convDone, open: false }
    }

    try {
      // Feature-centric layout: files live directly under pathly/features/<name>/.
      const featuresDir = `${projectPath}/pathly/features`
      const featureNames = (await listDirs(featuresDir).catch(() => [] as string[])).filter((n) => n !== '.archive')
      const folders: PlanFolder[] = []
      for (const name of featureNames) folders.push(await scanContent(name, `${featuresDir}/${name}`))
      setPlanFolders(folders)
    } catch {
      setPlanFolders([])
    }
  }, [projectPath])

  useEffect(() => {
    void loadPlanFiles()
    if (!projectPath) return
    const onWorkspaceChanged = window.pathly?.watch?.onWorkspaceChanged
    if (!onWorkspaceChanged) return
    return onWorkspaceChanged(() => { void loadPlanFiles() })
  }, [loadPlanFiles, projectPath])

  return { planFolders, setPlanFolders, loadPlanFiles }
}
