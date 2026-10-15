// HQ operator action catalog (pathly/features/local-operator): GET /hq/actions
// and PUT /hq/actions/available. Settings chooses which catalog actions HQ may
// use; the composer's Actions tab ticks from those. Fail-soft: null on error.
import { apiFetch } from '../lib/config'

export interface HqCatalogAction {
  name: string
  domain: string
  label: string
  /** In words: "changes state", "spends $", "hard to undo". */
  risk: string[]
  description: string
  runs_on: 'server' | 'studio'
  /** Allowed in Settings. */
  available: boolean
  default_available: boolean
  /** What offering it to the model costs (the composer's meter). */
  schema_tokens: number
}

export interface HqActionCatalog {
  max_enabled: number
  domains: { id: string; label: string }[]
  presets: { id: string; label: string; actions: string[] }[]
  actions: HqCatalogAction[]
}

export async function fetchHqActionCatalog(): Promise<HqActionCatalog | null> {
  try {
    const res = await apiFetch('/hq/actions')
    return res.ok ? (await res.json() as HqActionCatalog) : null
  } catch {
    return null
  }
}

export async function saveHqAvailableActions(names: string[]): Promise<HqActionCatalog | null> {
  try {
    const res = await apiFetch('/hq/actions/available', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actions: names }),
    })
    return res.ok ? (await res.json() as HqActionCatalog) : null
  } catch {
    return null
  }
}
