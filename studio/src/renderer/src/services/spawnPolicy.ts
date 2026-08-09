import { apiGetModelPolicy, type ModelPolicy } from '../store/commsApi'

// Client mirror of supervisor/spawn_policy.py::effective_model. Renderer one-shots (editor
// Split/Analyze/Diagram/Comment + artifact summaries) resolve their configured model here before
// spawning, so the Settings → Agents → Models "Editor / one-shot" rows actually take effect. Read
// from a warmed cache so resolution is SYNCHRONOUS at spawn time (the spawn/abort contract is
// sync). Fail-safe: an unwarmed cache or any miss returns the explicit model unchanged (engine
// default), behavior-identical to before this file existed.
let _policy: ModelPolicy | null = null

/** (Re)load the model policy into the shared cache. Fire-and-forget; called on module load and
 *  after a Settings edit (useModelPolicy). */
export async function warmModelPolicy(): Promise<void> {
  try {
    _policy = await apiGetModelPolicy()
  } catch {
    _policy = null // never let a warm (incl. the module-load one) throw / reject
  }
}

/** Sync mirror of the Python rule: an explicit model wins; otherwise the configured model for
 *  `role` (per-role override → global default) applies ONLY when it targets THIS run's `adapter`
 *  (model-within-company — a claude spawn never inherits a codex model); else `explicitModel`
 *  unchanged. Empty string means "engine default" (no --model flag). */
export function effectiveModel(role: string, adapter: string, explicitModel = ''): string {
  if (explicitModel || !role) return explicitModel
  const resolved = _policy?.roles?.[role] ?? _policy?.default ?? null
  if (resolved && resolved.model && resolved.adapter === adapter) return resolved.model
  return explicitModel
}

// Warm on first import (best-effort). A 404 (older FSM server) leaves the cache null → engine
// default everywhere, behavior-identical.
void warmModelPolicy()
