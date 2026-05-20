import { useProjectFiles } from '../../../../hooks/useProjectFiles'
import type { SectionState, PathlyItem } from '../../../../types'

export interface BehaviorItem {
  name: string
  kind: 'skill' | 'agent'
}

function sectionAllItems(s: SectionState | undefined): PathlyItem[] {
  if (!s) return []
  return [
    ...(s.items ?? []),
    ...(s.subdirs ?? []).flatMap((sd) => sd.files ?? []),
  ]
}

export function useBehaviorList(): BehaviorItem[] {
  const { sections } = useProjectFiles()

  return [
    ...['Skills', 'UserSkills', 'My Skills'].flatMap((key) =>
      sectionAllItems(sections[key]).map((item) => ({ name: item.name.replace(/\.[^.]+$/, ''), kind: 'skill' as const }))
    ),
    ...['Agents', 'UserAgents', 'My Agents'].flatMap((key) =>
      sectionAllItems(sections[key]).map((item) => ({ name: item.name.replace(/\.[^.]+$/, ''), kind: 'agent' as const }))
    ),
  ].filter((b, i, arr) => arr.findIndex((x) => x.name === b.name) === i)
}
