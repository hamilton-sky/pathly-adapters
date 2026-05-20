import { useCallback, useEffect, useState } from 'react'
import { useStore } from '../store'
import { listDir, listDirs, readFile } from '../services/pathlyApi'
import type { PathlyItem } from '../types'
import { parseProgressMd } from './usePlanConversations'

export interface PlanFolder {
  name: string
  path: string
  files: PathlyItem[]
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
    const plansDir = `${projectPath}/pathly/plans`
    try {
      const folderNames = await listDirs(plansDir)
      const folders: PlanFolder[] = []
      for (const name of folderNames) {
        const folderPath = `${plansDir}/${name}`
        let files: PathlyItem[] = []
        let convTotal = 0
        let convDone = 0
        try {
          const fileNames = await listDir(folderPath)
          files = fileNames.map((fname) => ({
            name: fname,
            path: `${folderPath}/${fname}`,
            type: 'plan' as const,
          }))
        } catch { /* empty folder */ }
        try {
          const md = await readFile(`${folderPath}/PROGRESS.md`)
          if (md) {
            const convs = parseProgressMd(md)
            convTotal = convs.length
            convDone = convs.filter((c) => c.status === 'DONE').length
          }
        } catch { /* no PROGRESS.md */ }
        folders.push({ name, path: folderPath, files, convTotal, convDone, open: false })
      }
      setPlanFolders(folders)
    } catch {
      setPlanFolders([])
    }
  }, [projectPath])

  useEffect(() => {
    void loadPlanFiles()
  }, [loadPlanFiles])

  return { planFolders, setPlanFolders, loadPlanFiles }
}
