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

// Per-project cache — keyed by projectPath (or '' for unknown).
const contextCache = new Map<string, { value: PathlyContext; expiresAt: number }>()

function fallbackContext(): PathlyContext {
  return { fsmStage: 'unknown', featureName: '', skills: KNOWN_SKILLS, studioSchema: getStudioSchema(), menu: null }
}

export async function buildPathlyContext(projectPath?: string): Promise<PathlyContext> {
  const cacheKey = projectPath ?? ''
  const now = Date.now()
  const cached = contextCache.get(cacheKey)
  if (cached && cached.expiresAt > now) return cached.value

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
    contextCache.set(cacheKey, { value, expiresAt: now + 3000 })
    return value
  } catch {
    const value = fallbackContext()
    contextCache.set(cacheKey, { value, expiresAt: now + 1000 })
    return value
  }
}

/** Force-expire the cache for a project so the next call re-fetches. */
export function invalidatePathlyContext(projectPath?: string): void {
  contextCache.delete(projectPath ?? '')
}

/**
 * Subscribe to real-time menu updates pushed by the FSM server via SSE.
 * Called whenever /next_action or /complete_stage produces a new menu.
 * Returns a cleanup function — call it on component unmount.
 */
export function subscribeToMenuUpdates(
  projectPath: string,
  onUpdate: (menu: PathlyMenu) => void
): () => void {
  let es: EventSource | null = null
  try {
    es = new EventSource(`${PATHLY_API_BASE}/events/menu`)
    es.onmessage = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data as string) as { type: string; menu?: PathlyMenu }
        if (data.type === 'MENU_UPDATE' && data.menu) {
          invalidatePathlyContext(projectPath)
          onUpdate(data.menu)
        }
      } catch { /* ignore parse errors */ }
    }
    es.onerror = () => {
      // EventSource auto-reconnects — nothing to do
    }
  } catch {
    // EventSource not available (e.g. unit test env) — silently skip
  }
  return () => { es?.close() }
}
