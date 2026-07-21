// Tiny service: fetch a flow's graph shape from the server. Isolates the GET
// /flows/<name>/graph fetch+parse concern so useFlowGateStages stays about composition,
// not HTTP — and so it is unit-testable on its own (DESIGN.md ss1a).

import { apiFetch } from '../../../lib/config'

export interface FlowGraph {
  states: string[]
  agentMap: Record<string, string>
  roleMap: Record<string, string>
}

/**
 * Fetch + parse a flow's graph ({graph:{states, agent_map, role_map, …}}). Returns null on
 * any failure (fail-soft) — the caller shows no stages and the gate falls back to a
 * plain-submit run.
 */
export async function fetchFlowGraph(name: string): Promise<FlowGraph | null> {
  if (!name) return null
  try {
    const r = await apiFetch(`/flows/${encodeURIComponent(name)}/graph`)
    if (!r.ok) return null
    const data = (await r.json()) as { graph?: Record<string, unknown> }
    const graph = data.graph
    if (!graph || typeof graph !== 'object') return null
    return {
      states: Array.isArray(graph.states) ? (graph.states as string[]) : [],
      agentMap: (graph.agent_map as Record<string, string> | undefined) ?? {},
      roleMap: (graph.role_map as Record<string, string> | undefined) ?? {},
    }
  } catch {
    return null
  }
}
