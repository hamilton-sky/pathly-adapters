import { useCallback, useEffect, useState } from 'react'
import { useStore } from '../../../store'
import { listAbilities } from '../../../services/abilities'
import { listUserPrompts } from '../../../services/promptLibrary'
import type { ProposedCell } from './SkillSplitModal'

// Drop a leading "# Title" line (+ its trailing blank) from an ability body — the cell already
// shows the title as its heading, so keeping it would double up in the assembled prompt.
function stripLeadingH1(body: string): string {
  const lines = body.split('\n')
  if (lines[0]?.startsWith('# ') && !lines[0].startsWith('## ')) {
    let i = 1
    while (i < lines.length && lines[i].trim() === '') i += 1
    return lines.slice(i).join('\n')
  }
  return body
}

// The two "tables" a user can ADD to a run's prompt from the Sections modal:
//   • abilities      — layer-3 .md files (pathly/abilities/ + ~/.pathly), open-in-editor via path
//   • system-prompts — the prompt_library presets (analyze/split/comment/diagram/system…)
// Both come back as UNCHECKED addable cells; checking one folds its body into the sent prompt.
// Creation lives in the Library, never here. Fetches only while `enabled` (the modal is open).
//
// Returns [cells, toggle] — a self-contained checked-state so the host just renders + reads them.
export function useLibraryCells(enabled: boolean): [ProposedCell[], (id: string) => void] {
  const projectPath = useStore((st) => st.projectPath)
  const [cells, setCells] = useState<ProposedCell[]>([])

  useEffect(() => {
    if (!enabled) {
      setCells([])
      return
    }
    let cancelled = false
    void Promise.all([
      listAbilities(projectPath),
      listUserPrompts({ kind: 'preset', projectRoot: projectPath }),
    ]).then(([abilities, prompts]) => {
      if (cancelled) return
      setCells([
        ...abilities.map((a) => ({
          id: `lib-ability:${a.id}`,
          type: 'markdown' as const,
          heading: a.label,
          content: stripLeadingH1(a.body),
          checked: false,
          layer: 'ability' as const,
          path: a.path,
        })),
        ...prompts.map((p) => ({
          id: `lib-system:${p.id}`,
          type: 'markdown' as const,
          heading: p.label,
          content: p.body,
          checked: false,
          layer: 'system' as const,
          path: p.path,
        })),
      ])
    })
    return () => {
      cancelled = true
    }
  }, [enabled, projectPath])

  const toggle = useCallback((id: string) => {
    setCells((prev) => prev.map((c) => (c.id === id ? { ...c, checked: !c.checked } : c)))
  }, [])

  return [cells, toggle]
}
