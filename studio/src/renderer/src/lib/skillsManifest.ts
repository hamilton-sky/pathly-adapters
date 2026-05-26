import skillsData from '../data/skills.json'

export interface Skill {
  name: string
  command: string
  description: string
  vector?: number[]
}

export function loadSkills(): Skill[] {
  return skillsData as Skill[]
}
