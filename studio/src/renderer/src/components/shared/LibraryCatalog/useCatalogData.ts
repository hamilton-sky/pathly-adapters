import { useEffect, useState } from 'react'

export interface CatalogItemData {
  name: string
  path?: string
  description?: string
  category?: string
}

export interface CatalogGroup {
  label: string
  type: 'agent' | 'fragment' | 'skill' | 'template'
  icon: 'brain' | 'diamond' | 'book-open' | 'layout-grid'
  items: CatalogItemData[]
}

interface Fragment {
  name: string
  description: string
  category: string
}

export function useCatalogData(pathlyRoot?: string): CatalogGroup[] {
  const [fragments, setFragments] = useState<CatalogItemData[]>([])
  const [agents, setAgents] = useState<CatalogItemData[]>([])
  const [skills, setSkills] = useState<CatalogItemData[]>([])
  const [templates, setTemplates] = useState<CatalogItemData[]>([])

  useEffect(() => {
    fetch('http://localhost:8765/skills/catalog')
      .then(r => r.json() as Promise<Fragment[]>)
      .then(data => setFragments(data.map(f => ({ name: f.name, description: f.description, category: f.category }))))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!pathlyRoot) return

    const agentsDir = `${pathlyRoot}/src/pathly_data/core/agents`
    const skillsDir = `${pathlyRoot}/src/pathly_data/core/skills`
    const templatesDir = `${pathlyRoot}/src/pathly_data/core/templates`

    window.pathly.fs.list(agentsDir)
      .then(files => setAgents(
        (files ?? []).map(f => ({ name: f, path: `${agentsDir}/${f}` }))
      ))
      .catch(() => {})

    window.pathly.fs.list(skillsDir)
      .then(files => setSkills(
        (files ?? []).map(f => ({ name: f, path: `${skillsDir}/${f}` }))
      ))
      .catch(() => {})

    window.pathly.fs.list(templatesDir)
      .then(files => setTemplates(
        (files ?? []).map(f => ({ name: f, path: `${templatesDir}/${f}` }))
      ))
      .catch(() => {})
  }, [pathlyRoot])

  const groups: CatalogGroup[] = []

  if (agents.length > 0) {
    groups.push({ label: 'Agents', type: 'agent', icon: 'brain', items: agents })
  }
  if (fragments.length > 0) {
    groups.push({ label: 'Fragments', type: 'fragment', icon: 'diamond', items: fragments })
  }
  if (skills.length > 0) {
    groups.push({ label: 'Skills', type: 'skill', icon: 'book-open', items: skills })
  }
  if (templates.length > 0) {
    groups.push({ label: 'Templates', type: 'template', icon: 'layout-grid', items: templates })
  }

  return groups
}
