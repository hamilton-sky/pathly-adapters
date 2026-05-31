import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { readFile } from '../services/pathlyApi'
import type { ConvRow } from '../types'

// Columns that are never the human-readable title
const SKIP_HEADERS = new Set(['conv', 'stories', 'status', 'verify', '#'])

export function parseProgressMd(md: string): ConvRow[] {
  const rows: ConvRow[] = []
  const lines = md.split('\n')

  let inSection = false
  let inFallbackTable = false
  let headerParsed = false
  let titleColIdx = 1
  let statusColIdx = 3
  let phasesColIdx = -1

  const hasBreakdownSection = lines.some((l) =>
    l.trim().startsWith('## Conversation Breakdown')
  )

  for (const line of lines) {
    const trimmed = line.trim()

    if (hasBreakdownSection) {
      if (trimmed.startsWith('## Conversation Breakdown')) { inSection = true; continue }
      if (inSection && trimmed.startsWith('##')) break
      if (!inSection) continue
    } else {
      // Fallback: parse the first markdown table in the file
      if (!inFallbackTable && trimmed.startsWith('|')) inFallbackTable = true
      if (inFallbackTable && trimmed && !trimmed.startsWith('|')) break
      if (!inFallbackTable) continue
    }

    if (!trimmed.startsWith('|')) continue
    const parts = trimmed.split('|').map((p) => p.trim()).filter(Boolean)

    if (!headerParsed) {
      headerParsed = true
      // Find title column: first column after Conv (index 0) not in SKIP_HEADERS
      for (let i = 1; i < parts.length; i++) {
        if (!SKIP_HEADERS.has(parts[i].toLowerCase())) { titleColIdx = i; break }
      }
      // Find status column: last column named 'status'
      for (let i = parts.length - 1; i >= 1; i--) {
        if (parts[i].toLowerCase() === 'status') { statusColIdx = i; break }
      }
      // Find phases column: column named 'phases'
      for (let i = 0; i < parts.length; i++) {
        if (parts[i].toLowerCase() === 'phases') { phasesColIdx = i; break }
      }
      continue
    }

    if (parts[0]?.startsWith('---')) continue
    const num = parseInt(parts[0], 10)
    if (isNaN(num)) continue
    const status = parts[statusColIdx] ?? parts[parts.length - 1] ?? ''
    const phases = phasesColIdx >= 0 ? (parts[phasesColIdx] ?? undefined) : undefined
    rows.push({ num, title: parts[titleColIdx] ?? '', status: status.toUpperCase(), phases })
  }
  return rows
}

export function usePlanConversations(topicOverride?: string | null): { planConvs: ConvRow[] } {
  const { projectPath, activeTopic } = useStore()
  const topic = topicOverride ?? activeTopic
  const [planConvs, setPlanConvs] = useState<ConvRow[]>([])

  useEffect(() => {
    if (!projectPath || !topic) { setPlanConvs([]); return }
    async function loadPlan(): Promise<void> {
      try {
        const md = await readFile(`${projectPath}/pathly/plans/${topic}/PROGRESS.md`)
        if (!md) { setPlanConvs([]); return }
        setPlanConvs(parseProgressMd(md))
      } catch { setPlanConvs([]) }
    }
    void loadPlan()
  }, [projectPath, topic])

  return { planConvs }
}
