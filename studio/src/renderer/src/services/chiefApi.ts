// The chief's session routes (pathly/features/chief-agent): GET /chief/presets, GET
// /chief/session, POST /chief/open, POST /chief/close. The server resolves a chief's tier from the
// preset name and enforces it; Studio only shows what these routes report. Reads are fail-soft
// (null on error); open reports the server's error text so the launcher can show it.
import { apiFetch } from '../lib/config'

export type ChiefTier = 'status' | 'planner' | 'operator'

export interface ChiefPreset {
  name: string
  label: string
  tier: ChiefTier
  /** The style as stored, front matter included. */
  text: string
  source: 'builtin' | 'user'
  scope: 'project' | 'global' | null
}

export interface ChiefPresetList {
  presets: ChiefPreset[]
  /** What each tier may do, in the gate's own action names. */
  tiers: Record<ChiefTier, string[]>
  /** The limits a chief opened now gets (GET /chief/session reports them only while one is open). */
  limits: { max_runs_per_session: number; max_cost_usd_per_run: number }
}

export type ChiefSession =
  | { open: false }
  | {
      open: true
      run_id: string
      tab_id: string
      tier: ChiefTier
      engine: string
      opened_at: number
      runs_started: number
      max_runs_per_session: number
      max_cost_usd_per_run: number
    }

export interface OpenChiefRequest {
  projectRoot: string
  engine: string
  preset: string
  /** Sent only when the user edited the style; otherwise the server uses the preset's text. */
  prompt?: string
}

export type OpenChiefResult =
  | { ok: true; run_id: string; tab_id: string; tier: ChiefTier }
  | { ok: false; status: number; error: string }

const q = (projectRoot: string): string =>
  `project_root=${encodeURIComponent(projectRoot)}`

export async function fetchChiefPresets(projectRoot: string): Promise<ChiefPresetList | null> {
  try {
    const res = await apiFetch(`/chief/presets?${q(projectRoot)}`)
    return res.ok ? ((await res.json()) as ChiefPresetList) : null
  } catch {
    return null
  }
}

export async function fetchChiefSession(projectRoot: string): Promise<ChiefSession | null> {
  try {
    const res = await apiFetch(`/chief/session?${q(projectRoot)}`)
    return res.ok ? ((await res.json()) as ChiefSession) : null
  } catch {
    return null
  }
}

export async function openChief(req: OpenChiefRequest): Promise<OpenChiefResult> {
  const body: Record<string, string> = {
    project_root: req.projectRoot,
    engine: req.engine,
    preset: req.preset,
  }
  if (req.prompt !== undefined) body.prompt = req.prompt
  try {
    const res = await apiFetch('/chief/open', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = (await res.json().catch(() => ({}))) as Record<string, unknown>
    if (res.ok) {
      return {
        ok: true,
        run_id: String(data.run_id),
        tab_id: String(data.tab_id),
        tier: data.tier as ChiefTier,
      }
    }
    return { ok: false, status: res.status, error: String(data.error ?? `HTTP ${res.status}`) }
  } catch (err) {
    return { ok: false, status: 0, error: `Pathly server unreachable: ${String(err)}` }
  }
}

export async function closeChief(projectRoot: string): Promise<boolean | null> {
  try {
    const res = await apiFetch('/chief/close', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_root: projectRoot }),
    })
    if (!res.ok) return null
    const data = (await res.json()) as { closed?: boolean }
    return Boolean(data.closed)
  } catch {
    return null
  }
}
