import { useEffect, useState } from 'react'
import { useStore } from '../../../store'
import { listDirs } from '../../../services/pathlyApi'
import { fetchDbFeatureMap } from '../../../store/commsApi'
import type { PlanRow, ProjectPlans } from '../types'

const ROOTS: Array<{ subdir: string; flowType: 'team' | 'debug' | 'explore' }> = [
  { subdir: 'pathly/features',     flowType: 'team'    },
  { subdir: 'pathly/debugs',       flowType: 'debug'   },
  { subdir: 'pathly/explorations', flowType: 'explore' },
]

async function scanRoot(
  projectPath: string,
  subdir: string,
  flowType: 'team' | 'debug' | 'explore',
  dbFeatures: Map<string, DbFeature>
): Promise<PlanRow[]> {
  const dir = `${projectPath}/${subdir}`
  const folders = await listDirs(dir).catch(() => [] as string[])
  const rows: PlanRow[] = []
  for (const folder of folders) {
    if (folder === '.archive') continue
    // State joins from the DB-first /db/features row (state-one-authority) — the
    // folder listing stays the source of WHICH plans exist in each root.
    const state = dbFeatures.get(folder)?.state
    rows.push({ name: folder, state: state && state !== 'UNKNOWN' ? state : '', flowType })
  }
  return rows
}

export function useProjectPlans(): ProjectPlans {
  const { projects, updateProject } = useStore()
  const [projectPlans, setProjectPlans] = useState<ProjectPlans>({})

  useEffect(() => {
    async function loadAllPlans(): Promise<void> {
      const result: ProjectPlans = {}
      for (const project of projects) {
        try {
          // One DB fetch per project — replaces the per-folder STATE.json reads.
          const dbFeatures = await fetchDbFeatureMap(project.path)
          const allRows: PlanRow[] = []
          for (const root of ROOTS) {
            const rows = await scanRoot(project.path, root.subdir, root.flowType, dbFeatures)
            allRows.push(...rows)
          }
          result[project.path] = allRows
          const active = allRows.find((r) => r.state && r.state !== 'DONE' && r.state !== 'IDLE')
          updateProject(project.path, {
            activeTopic: active?.name ?? allRows[0]?.name,
            fsmState: active?.state ?? allRows[0]?.state ?? ''
          })
        } catch {
          result[project.path] = []
        }
      }
      setProjectPlans(result)
    }
    loadAllPlans()
  }, [projects.length]) // eslint-disable-line react-hooks/exhaustive-deps

  return projectPlans
}
