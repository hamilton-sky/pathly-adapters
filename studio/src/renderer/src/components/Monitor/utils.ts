import { useEffect, useRef } from 'react'
import { useStore } from '../../store'
import type { FsmEvent } from '../../types/index'

export function formatRelativeTime(ts: string): string {
  const diffMs = Date.now() - new Date(ts).getTime()
  const diffS = Math.floor(diffMs / 1000)
  if (diffS < 60) return 'now'
  const diffM = Math.floor(diffS / 60)
  if (diffM < 60) return `${diffM}m ago`
  return `${Math.floor(diffM / 60)}h ago`
}

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

export interface AgentTelemetry {
  agentDone: FsmEvent[]
  totalIn: number
  totalOut: number
  totalTokens: number
  lastWall: number | undefined
  totalCost: number
  hasTelemetry: boolean
  noTelemetry: boolean
  eventsCount: number
}

function eventTokens(e: FsmEvent): number {
  const inOut = (e.tokens_in ?? 0) + (e.tokens_out ?? 0)
  // fall back to total_tokens for events written before the in/out split was added
  return inOut > 0 ? inOut : ((e as Record<string, unknown>).total_tokens as number | undefined ?? 0)
}

export function useAgentTelemetry(): AgentTelemetry {
  const events = useStore((s) => s.events)
  const agentDone = events.filter((e) => e.type === 'AGENT_DONE')
  const totalIn = agentDone.reduce((s, e) => s + (e.tokens_in ?? 0), 0)
  const totalOut = agentDone.reduce((s, e) => s + (e.tokens_out ?? 0), 0)
  const totalCost = agentDone.reduce((s, e) => s + (e.cost_usd ?? 0), 0)
  const totalTokens = totalIn + totalOut > 0
    ? totalIn + totalOut
    : agentDone.reduce((s, e) => s + eventTokens(e), 0)
  return {
    agentDone,
    totalIn,
    totalOut,
    totalTokens,
    lastWall: agentDone.length > 0 ? agentDone[agentDone.length - 1].wall_seconds : undefined,
    totalCost,
    hasTelemetry: agentDone.length > 0,
    noTelemetry: events.length > 0 && agentDone.length === 0,
    eventsCount: events.length,
  }
}

export function getFlowYamlName(flow: string | undefined): string {
  switch (flow) {
    case 'team': return 'team.flow.yaml'
    case 'debug': return 'debug.flow.yaml'
    case 'explore': return 'explore.flow.yaml'
    default:
      if (flow !== undefined) {
        console.warn(`[Monitor] Unknown flow type "${flow}", falling back to team.flow.yaml`)
      }
      return 'team.flow.yaml'
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

export function fmtTokens(n: number): string {
  if (n === 0) return '—'
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

export function fmtWall(n: number | undefined): string {
  return n == null ? '—' : `${n}s`
}

export function fmtCost(n: number): string {
  return n === 0 ? '—' : `$${n.toFixed(2)}`
}

export const EMPTY_TOOLTIP = 'Waiting for AGENT_DONE events with telemetry'

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
