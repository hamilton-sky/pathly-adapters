import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { readFile } from '../services/pathlyApi'
import type { ConvRow } from '../types'

function parseProgressMd(md: string): ConvRow[] {
  const rows: ConvRow[] = []
  const lines = md.split('\n')
  let inSection = false
  let headerParsed = false
  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('## Conversation Breakdown')) { inSection = true; continue }
    if (inSection && trimmed.startsWith('##')) break
    if (!inSection) continue
    if (!trimmed.startsWith('|')) continue
    const parts = trimmed.split('|').map((p) => p.trim()).filter(Boolean)
    if (!headerParsed) { headerParsed = true; continue }
    if (parts[0]?.startsWith('---')) continue
    const num = parseInt(parts[0], 10)
    if (isNaN(num)) continue
    // columns: Conv, Phases(title), Stories, Status — NOT the last Verify column
    const status = parts[3] ?? ''
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
        if (!md) { setPlanConvs([]); return }
        setPlanConvs(parseProgressMd(md))
      } catch { setPlanConvs([]) }
    }
    void loadPlan()
  }, [projectPath, activeTopic])

  return { planConvs }
}
