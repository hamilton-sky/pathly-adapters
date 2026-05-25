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

export function useAgentTelemetry(): AgentTelemetry {
  const events = useStore((s) => s.events)
  const agentDone = events.filter((e) => e.type === 'AGENT_DONE')
  const totalIn = agentDone.reduce((s, e) => s + (e.tokens_in ?? 0), 0)
  const totalOut = agentDone.reduce((s, e) => s + (e.tokens_out ?? 0), 0)
  const totalCost = agentDone.reduce((s, e) => s + (e.cost_usd ?? 0), 0)
  return {
    agentDone,
    totalIn,
    totalOut,
    totalTokens: totalIn + totalOut,
    lastWall: agentDone.length > 0 ? agentDone[agentDone.length - 1].wall_seconds : undefined,
    totalCost,
    hasTelemetry: agentDone.length > 0,
    noTelemetry: events.length > 0 && agentDone.length === 0,
    eventsCount: events.length,
  }
}
