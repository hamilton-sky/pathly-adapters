import { PATHLY_API_BASE } from './config'
import { getStudioSchema } from './studioSchema'
import { StudioElement } from '../types/studio'

export interface PathlyContext {
  fsmStage: string
  featureName: string
  skills: string[]
  studioSchema: StudioElement[]
  menu: PathlyMenu | null
}

export interface PathlyMenuItem {
  label: string
  description: string
  command: string
  target_state?: string
  terminal_kind?: 'claude' | 'codex' | 'shell'
}

export interface PathlyMenu {
  state: string
  feature: string
  agent: string
  title: string
  subtitle: string
  items: PathlyMenuItem[]
  empty_message: string
}

const KNOWN_SKILLS = [
  'plan', 'po', 'storm', 'build', 'review', 'test', 'retro',
  'explore', 'debug', 'design', 'fix', 'status', 'log', 'end',
]

let cachedContext: { value: PathlyContext; expiresAt: number } | null = null

function fallbackContext(): PathlyContext {
  return { fsmStage: 'unknown', featureName: '', skills: KNOWN_SKILLS, studioSchema: getStudioSchema(), menu: null }
}

export async function buildPathlyContext(projectPath?: string): Promise<PathlyContext> {
  const now = Date.now()
  if (cachedContext && cachedContext.expiresAt > now) return cachedContext.value

  const studioSchema = getStudioSchema()
  try {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 750)
    const url = projectPath
      ? `${PATHLY_API_BASE}/status?project_root=${encodeURIComponent(projectPath)}`
      : `${PATHLY_API_BASE}/status`
    const res = await fetch(url, { signal: controller.signal })
    window.clearTimeout(timeout)
    const data = await res.json() as { current_state?: string; feature?: string; menu?: PathlyMenu | null }
    const value = {
      fsmStage: data.current_state ?? 'unknown',
      featureName: data.feature ?? '',
      skills: KNOWN_SKILLS,
      studioSchema,
      menu: data.menu ?? null,
    }
    cachedContext = { value, expiresAt: now + 3000 }
    return value
  } catch {
    const value = fallbackContext()
    cachedContext = { value, expiresAt: now + 1000 }
    return value
  }
}
