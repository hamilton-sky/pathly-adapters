import { useEffect, useState } from 'react'
import * as jsYaml from 'js-yaml'
import { useProjectFiles } from '../../../../hooks/useProjectFiles'
import { readFile } from '../../../../services/pathlyApi'
import type { SectionState, PathlyItem } from '../../../../types'

function sectionAllItems(s: SectionState | undefined): PathlyItem[] {
  if (!s) return []
  return [
    ...(s.items ?? []),
    ...(s.subdirs ?? []).flatMap((sd) => sd.files ?? []),
  ]
}

export function useRequiredArtifacts(currentAgent: string): string[] | null {
  const { sections } = useProjectFiles()
  const [requiredArtifacts, setRequiredArtifacts] = useState<string[] | null>(null)

  useEffect(() => {
    setRequiredArtifacts(null)
    if (!currentAgent) return
    const allItems = [
      ...['Skills', 'UserSkills', 'My Skills'].flatMap((k) => sectionAllItems(sections[k])),
      ...['Agents', 'UserAgents', 'My Agents'].flatMap((k) => sectionAllItems(sections[k])),
    ]
    const item = allItems.find((i) => i.name.replace(/\.[^.]+$/, '') === currentAgent)
    if (!item) return
    readFile(item.path)
      .then((content) => {
        const fmMatch = content.match(/^---\r?\n([\s\S]*?)\r?\n---/)
        if (!fmMatch) return
        const fm = jsYaml.load(fmMatch[1]) as Record<string, unknown> | null
        if (!fm) return
        const artifacts = fm['required_artifacts']
        setRequiredArtifacts(Array.isArray(artifacts) && artifacts.length > 0 ? artifacts.map(String) : [])
      })
      .catch(() => { /* unreadable */ })
  }, [currentAgent, sections])

  return requiredArtifacts
}
