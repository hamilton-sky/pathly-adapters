import { useEffect, useState } from 'react'
import { useStore } from '../../../store'
import { listDirs, readFile } from '../../../services/pathlyApi'
import type { PlanRow, ProjectPlans } from '../types'

const ROOTS: Array<{ subdir: string; flowType: 'team' | 'debug' | 'explore' }> = [
  { subdir: 'pathly/plans',        flowType: 'team'    },
  { subdir: 'pathly/debugs',       flowType: 'debug'   },
  { subdir: 'pathly/explorations', flowType: 'explore' },
]

async function scanRoot(
  projectPath: string,
  subdir: string,
  flowType: 'team' | 'debug' | 'explore'
): Promise<PlanRow[]> {
  const dir = `${projectPath}/${subdir}`
  const folders = await listDirs(dir).catch(() => [] as string[])
  const rows: PlanRow[] = []
  for (const folder of folders) {
    if (folder === '.archive') continue
    try {
      const raw = await readFile(`${dir}/${folder}/STATE.json`)
      const parsed = JSON.parse(raw ?? '{}') as { current?: string }
      rows.push({ name: folder, state: parsed.current ?? '', flowType })
    } catch {
      rows.push({ name: folder, state: '', flowType })
    }
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
          const allRows: PlanRow[] = []
          for (const root of ROOTS) {
            const rows = await scanRoot(project.path, root.subdir, root.flowType)
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
