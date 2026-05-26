import { PATHLY_API_BASE } from './config'
import { getStudioSchema } from './studioSchema'
import { StudioElement } from '../types/studio'

export interface PathlyContext {
  fsmStage: string
  featureName: string
  skills: string[]
  studioSchema: StudioElement[]
}

const KNOWN_SKILLS = [
  'plan', 'po', 'storm', 'build', 'review', 'test', 'retro',
  'explore', 'debug', 'design', 'fix', 'status', 'log', 'end',
]

export async function buildPathlyContext(): Promise<PathlyContext> {
  const studioSchema = getStudioSchema()
  try {
    const res = await fetch(`${PATHLY_API_BASE}/status`)
    const data = await res.json() as { current_state?: string; feature?: string }
    return {
      fsmStage: data.current_state ?? 'unknown',
      featureName: data.feature ?? '',
      skills: KNOWN_SKILLS,
      studioSchema,
    }
  } catch {
    return { fsmStage: 'unknown', featureName: '', skills: KNOWN_SKILLS, studioSchema }
  }
}
