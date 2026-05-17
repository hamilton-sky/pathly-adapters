import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { readFile } from '../services/pathlyApi'
import type { ConvRow } from '../types'

function parseProgressMd(md: string): ConvRow[] {
  const rows: ConvRow[] = []
  let headerParsed = false
  for (const line of md.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed.startsWith('|')) continue
    const parts = trimmed.split('|').map((p) => p.trim()).filter(Boolean)
    if (!headerParsed) { headerParsed = true; continue }
    if (parts[0]?.startsWith('---')) continue
    const num = parseInt(parts[0], 10)
    if (isNaN(num)) continue
    const status = parts[parts.length - 1] ?? ''
    rows.push({ num, title: parts[1] ?? '', status: status.toUpperCase() })
  }
  return rows
}

export function usePlanConversations(): { planConvs: ConvRow[] } {
  const { projectPath, activeTopic } = useStore()
  const [planConvs, setPlanConvs] = useState<ConvRow[]>([])

  useEffect(() => {
    if (!projectPath || !activeTopic) { setPlanConvs([]); return }
    async function loadPlan(): Promise<void> {
      try {
        const md = await readFile(`${projectPath}/pathly/plans/${activeTopic}/PROGRESS.md`)
        setPlanConvs(parseProgressMd(md))
      } catch { setPlanConvs([]) }
    }
    void loadPlan()
  }, [projectPath, activeTopic])

  return { planConvs }
}
