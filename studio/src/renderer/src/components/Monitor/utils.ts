import { useEffect, useRef } from 'react'
import * as jsYaml from 'js-yaml'
import type { FsmEvent, FlowYaml } from '../../types/index'

export function useInjectCSS(css: string): void {
  const injectedRef = useRef(false)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (injectedRef.current) return
    injectedRef.current = true
    const style = document.createElement('style')
    style.textContent = css
    document.head.appendChild(style)
  }, [])
}

// Every flow file is named `<flow>.flow.yaml` (team, team-build, debug, explore,
// consultation, feature-consultation, project-consultation, quick-fix, test), so the
// mapping is generic. A missing file is handled by the caller's .catch (FsmView falls
// back to a default pipeline). Empty flow → the full team pipeline.
export function getFlowYamlName(flow: string | undefined): string {
  return flow ? `${flow}.flow.yaml` : 'team.flow.yaml'
}

export interface ParsedFlowStages {
  states: string[]
  roles: Record<string, string>   // stage → agent role   (flow `role_map`)
  skills: Record<string, string>  // stage → skill         (flow `agent_map`)
}

/**
 * Extract the stepper + per-stage config from an already-parsed flow graph — the
 * FlowYaml-shaped dict returned by GET /flows/<name>/graph (the DB-authoritative
 * runtime flow, covering seed, user-edited, AND user-created flows). States are
 * uppercased to match FSM state names in STATE.json. `role_map`/`agent_map` are the
 * flow's OWN per-stage agent/skill assignments — the single source that lets the
 * stepper label and the Configure-phase modal adapt to any flow. Null on empty input.
 */
export function parseFlowGraph(doc: Partial<FlowYaml> | null | undefined): ParsedFlowStages | null {
  if (!doc || typeof doc !== 'object') return null

  const states = Array.isArray(doc.states)
    ? doc.states.map((s) => String(s).trim().toUpperCase()).filter(Boolean)
    : []
  if (states.length === 0) return null

  const upperKeys = (m: Record<string, string> | undefined): Record<string, string> => {
    const out: Record<string, string> = {}
    if (m && typeof m === 'object') {
      for (const [k, v] of Object.entries(m)) {
        if (v != null) out[k.trim().toUpperCase()] = String(v)
      }
    }
    return out
  }

  return { states, roles: upperKeys(doc.role_map), skills: upperKeys(doc.agent_map) }
}

/**
 * Parse a .flow.yaml seed file's stage metadata (resilience fallback used only when
 * the DB graph is unavailable). Real YAML parse — not a regex, which missed the
 * non-indented dash lists in team-build.flow.yaml.
 */
export function parseFlowStages(yamlText: string): ParsedFlowStages | null {
  try {
    return parseFlowGraph(jsYaml.load(yamlText) as Partial<FlowYaml> | null)
  } catch {
    return null
  }
}

export function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max) + '…' : s
}

export function extractTopic(sessionKey: string): string {
  const slash = sessionKey.indexOf('/')
  return slash === -1 ? sessionKey : sessionKey.slice(slash + 1)
}

export function flowTypeLabel(flowKey: string): string {
  // The flow's real name (team/debug/explore/…). Historically the team flow was
  // relabeled 'plan' here, which rendered as `plan/<topic>` — indistinguishable from
  // the retired pathly/plans/ folder. Show the honest flow name instead.
  return flowKey.replace('.flow.yaml', '') || 'team'
}

/**
 * Merge a BILLING_UPDATE event into its corresponding AGENT_DONE entry.
 * Finds the last AGENT_DONE for the same (agent, conversation) and overlays
 * the corrected cost/token/tool fields, then drops the BILLING_UPDATE itself.
 * Called by the SSE message handler so Studio shows correct values after
 * _patch_last_agent_done rewrites a line in-place.
 */
export function mergeBillingUpdate(events: FsmEvent[], update: FsmEvent): FsmEvent[] {
  let lastIdx = -1
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i]
    if (e.type === 'AGENT_DONE' && e.agent === update.agent && e.conversation === update.conversation) {
      lastIdx = i
      break
    }
  }
  if (lastIdx === -1) return events
  const result = [...events]
  result[lastIdx] = {
    ...result[lastIdx],
    tool_uses: update.tool_uses ?? result[lastIdx].tool_uses,
    wall_seconds: update.wall_seconds ?? result[lastIdx].wall_seconds,
    cost_usd: update.cost_usd ?? result[lastIdx].cost_usd,
    tokens_in: update.tokens_in ?? result[lastIdx].tokens_in,
    tokens_out: update.tokens_out ?? result[lastIdx].tokens_out,
  }
  return result
}
