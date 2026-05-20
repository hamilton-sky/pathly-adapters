import { useMemo } from 'react'
import type { SectionState } from '../../../../types'
import { useProjectFiles } from '../../../../hooks/useProjectFiles'

export function useKnownBehaviors(): string[] {
  const { sections } = useProjectFiles()

  return useMemo(() => {
    const all = (s: SectionState | undefined) => [
      ...(s?.items ?? []),
      ...(s?.subdirs ?? []).flatMap((sd) => sd.files ?? []),
    ]
    const names = [
      ...['Skills', 'UserSkills', 'My Skills'].flatMap((k) => all(sections[k]).map((i) => i.name.replace(/\.[^.]+$/, ''))),
      ...['Agents', 'UserAgents', 'My Agents'].flatMap((k) => all(sections[k]).map((i) => i.name.replace(/\.[^.]+$/, ''))),
    ]
    return [...new Set(names)]
  }, [sections])
}
