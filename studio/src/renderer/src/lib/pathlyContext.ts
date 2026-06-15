import { PATHLY_API_BASE, apiFetch } from './config'
import { getStudioSchema } from './studioSchema'
import { StudioElement } from '../types/studio'

export interface PathlyContext {
  fsmStage: string
  featureName: string
  skills: string[]
  studioSchema: StudioElement[]
  menu: PathlyMenu | null       // pipeline menu — FSM-state-driven, from /status
  pushedMenu: PushedMenu | null // transient menu — skill-triggered, from /menu/{name}
}

export interface PushedMenu extends PathlyMenu {
  ttl: number      // total TTL in seconds
  pushedAt: number // ms timestamp when the server pushed this menu
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
  return { fsmStage: 'unknown', featureName: '', skills: KNOWN_SKILLS, studioSchema: getStudioSchema(), menu: null, pushedMenu: null }
}

export async function buildPathlyContext(projectPath?: string, topic?: string): Promise<PathlyContext> {
  const cacheKey = `${projectPath ?? ''}:${topic ?? ''}`
  const now = Date.now()
  const cached = contextCache.get(cacheKey)
  if (cached && cached.expiresAt > now) return cached.value

  const studioSchema = getStudioSchema()
  try {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 750)
    let path = projectPath
      ? `/status?project_root=${encodeURIComponent(projectPath)}`
      : `/status`
    if (topic) path += `&topic=${encodeURIComponent(topic)}`
    const res = await apiFetch(path, { signal: controller.signal })
    window.clearTimeout(timeout)
    const data = await res.json() as { current_state?: string; feature?: string; menu?: PathlyMenu | null }
    const value = {
      fsmStage: data.current_state ?? 'unknown',
      featureName: data.feature ?? '',
      skills: KNOWN_SKILLS,
      studioSchema,
      menu: data.menu ?? null,
      pushedMenu: null, // pushed menus arrive via SSE only, not polling
    }
    contextCache.set(cacheKey, { value, expiresAt: now + 3000 })
    return value
  } catch {
    const value = fallbackContext()
    contextCache.set(cacheKey, { value, expiresAt: now + 1000 })
    return value
  }
}

/** Force-expire all cached entries for a project (all topics) so the next call re-fetches. */
export function invalidatePathlyContext(projectPath?: string): void {
  const prefix = projectPath ?? ''
  for (const key of Array.from(contextCache.keys())) {
    if (key === prefix || key === `${prefix}:` || key.startsWith(`${prefix}:`)) {
      contextCache.delete(key)
    }
  }
}

/**
 * Subscribe to real-time menu events from the FSM server via SSE.
 *
 * MENU_UPDATE  — pipeline menu changed (FSM state transition)
 * MENU_PUSH    — transient menu pushed by a skill via GET /menu/{name}
 * MENU_CLEAR   — pushed menu TTL expired (server-side timer fired)
 *
 * Returns a cleanup function — call it on component unmount.
 */
export function subscribeToMenuUpdates(
  projectPath: string,
  onPipelineUpdate: (menu: PathlyMenu) => void,
  onPushedUpdate: (menu: PushedMenu) => void,
  onPushedClear: () => void,
): () => void {
  let es: EventSource | null = null
  try {
    es = new EventSource(`${PATHLY_API_BASE}/events/menu`)
    es.onmessage = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data as string) as {
          type: string
          menu?: PathlyMenu & { ttl?: number; pushed_at?: number }
        }
        if (data.type === 'MENU_UPDATE' && data.menu) {
          invalidatePathlyContext(projectPath)
          onPipelineUpdate(data.menu)
        } else if (data.type === 'MENU_PUSH' && data.menu) {
          onPushedUpdate({
            ...data.menu,
            ttl: data.menu.ttl ?? 60,
            pushedAt: data.menu.pushed_at ?? Date.now(),
          })
        } else if (data.type === 'MENU_CLEAR') {
          onPushedClear()
        }
      } catch { /* ignore parse errors */ }
    }
    es.onerror = () => { /* EventSource auto-reconnects */ }
  } catch {
    // EventSource not available (e.g. unit test env) — silently skip
  }
  return () => { es?.close() }
}
