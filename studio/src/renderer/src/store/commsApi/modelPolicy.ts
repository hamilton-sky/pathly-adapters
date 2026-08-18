// spawn-policy: the per-agent model policy, the agent registry that drives its rows, and the
// provider pricing table its dropdowns render.

import { apiFetch } from '../../lib/config'

// spawn's model + narration are chosen the same way everywhere. Mirrors the default-progress
// pair above. The always-on cost/monitor spine is deliberately NOT exposed (SPEC §0 invariant).

/** One {company, model} selection. `model` '' = that company's own engine default. */
export interface ModelSel {
  adapter: string
  model: string
}

/** The full per-agent model policy for the Settings UI. */
export interface ModelPolicy {
  /** Global default applied to every spawn without a per-role override; null = engine default. */
  default: ModelSel | null
  /** Per-role/per-place overrides, keyed by the agent/telemetry identity (architect, split, …). */
  roles: Record<string, ModelSel>
}

/** Fetch the per-agent model policy, or null on error. */
export async function apiGetModelPolicy(): Promise<ModelPolicy | null> {
  try {
    const r = await apiFetch('/comms/model-policy')
    if (!r.ok) return null
    const j = (await r.json()) as Partial<ModelPolicy>
    return { default: j.default ?? null, roles: j.roles ?? {} }
  } catch {
    return null
  }
}

/** Set the global default (role null) or a per-role override. `model` '' = engine default. */
export async function apiSetModelPolicy(
  role: string | null,
  adapter: string,
  model: string,
): Promise<boolean> {
  try {
    const r = await apiFetch('/comms/model-policy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role, adapter, model }),
    })
    return r.ok
  } catch {
    return false
  }
}

/** Clear the global default (role null) or a per-role override (falls back to the default). */
export async function apiClearModelPolicy(role: string | null): Promise<boolean> {
  try {
    const r = await apiFetch('/comms/model-policy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role, clear: true }),
    })
    return r.ok
  } catch {
    return false
  }
}

/** One agent role from the registry (seeded from core/agents/), for the model-policy UI. */
export interface AgentDef {
  role: string
  name: string
  model: string
  description: string
}

/** Fetch the known agent roles from the registry, or [] on error (UI falls back to built-ins). */
export async function apiGetAgents(projectRoot?: string): Promise<AgentDef[]> {
  try {
    const q = projectRoot ? `?project_root=${encodeURIComponent(projectRoot)}` : ''
    const r = await apiFetch(`/db/agents${q}`)
    if (!r.ok) return []
    const j = (await r.json()) as { agents?: AgentDef[] }
    return Array.isArray(j.agents) ? j.agents : []
  } catch {
    return []
  }
}

/** A priced model row (one model + its $/MTok rates), for the model dropdowns. */
export interface PricingModel {
  model: string
  input: number
  output: number
}
/** Priced models keyed by provider slug (claude/codex/antigravity/…). */
export type PricingByProvider = Record<string, PricingModel[]>

/** Fetch the provider pricing table (models per provider + $/MTok), or {} on error. */
export async function apiGetPricing(): Promise<PricingByProvider> {
  try {
    const r = await apiFetch('/telemetry/pricing')
    if (!r.ok) return {}
    const j = (await r.json()) as {
      providers?: Record<string, Record<string, { input: number; output: number }>>
    }
    const out: PricingByProvider = {}
    for (const [provider, models] of Object.entries(j.providers ?? {})) {
      out[provider] = Object.entries(models).map(([model, rate]) => ({
        model,
        input: rate.input,
        output: rate.output,
      }))
    }
    return out
  } catch {
    return {}
  }
}
