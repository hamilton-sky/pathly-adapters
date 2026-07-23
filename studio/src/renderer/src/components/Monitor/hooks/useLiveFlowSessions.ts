import { useEffect, useRef } from 'react'
import { useStore } from '../../../store'
import { useUiStore } from '../../../store/uiStore'
import { useTerminalStore } from '../../../store/terminalStore'
import { fetchDbFeatureMap } from '../../../store/commsApi'
import { extractTopic, upsertSessionByTopic } from '../utils'
import type { FlowSession } from '../../../types/index'

/**
 * Last path segment of a runner topic. Board-scoped runs nest under their board
 * (`features/<feature>/goals/<slug>`), but the FSM keys state + events by the bare
 * storage-dir slug — which is also the /db/features row key the stepper hydrates from.
 */
function topicSlug(feature: string | undefined): string | null {
  if (!feature || feature === '(project)') return null
  const parts = feature.split('/').filter(Boolean)
  return parts.length > 0 ? parts[parts.length - 1] : null
}

/**
 * Seed the flow dock's sessions/tabs from the LIVE spawn gate — the same authoritative
 * `spawnQueue.engines` list the engine board projects. Every running (or queued) engine with
 * `category:'flow'` registers a session for its run slug and auto-selects its tab the first
 * time it appears, so the dock always steps through the flow the user just spawned (goal team
 * runs included — those are not plan folders, so the DB folder scan alone never saw them).
 * `isRunning` is engine-backed liveness: it flips true only while the gate holds a flow engine
 * for the topic, which is what the tab dot and running-first tab order key off.
 */
export function useLiveFlowSessions(): void {
  const engines = useTerminalStore((s) => s.spawnQueue.engines)
  const queued = useTerminalStore((s) => s.spawnQueue.queuedEngines)
  const projectPath = useStore((s) => s.projectPath)

  // Topics already auto-selected once — a flow drops off the gate between stage PTYs, and its
  // reappearance must not yank the user's tab choice again.
  const seenRef = useRef<Set<string>>(new Set())

  // Reset the auto-select memory with the sessions themselves on project switch.
  useEffect(() => {
    seenRef.current = new Set()
  }, [projectPath])

  useEffect(() => {
    if (!projectPath) return

    // topic slug → newest spawn time among its live/queued flow engines.
    const live = new Map<string, number>()
    for (const e of [...engines, ...queued]) {
      if ((e.category ?? 'single') !== 'flow') continue
      const slug = topicSlug(e.feature)
      if (!slug) continue
      live.set(slug, Math.max(live.get(slug) ?? 0, e.startedAt ?? 0))
    }

    // Sync isRunning on existing sessions (dot on = an engine is actually live right now).
    // Imperative store access goes through the REAL zustand store (useUiStore) — the merged
    // useStore facade is a plain hook with no .getState.
    const { setActiveFlowSessions } = useUiStore.getState()
    setActiveFlowSessions((prev) => {
      let changed = false
      const next: Record<string, FlowSession> = {}
      for (const [k, s] of Object.entries(prev)) {
        const isLive = live.has(extractTopic(k))
        if (s.isRunning !== isLive) {
          changed = true
          next[k] = { ...s, isRunning: isLive }
        } else {
          next[k] = s
        }
      }
      return changed ? next : prev
    })

    const fresh = [...live.keys()].filter((t) => !seenRef.current.has(t))
    if (fresh.length === 0) return
    for (const t of fresh) seenRef.current.add(t)

    // Register the freshly spawned flows (flow name from the DB row; 'team' until it lands)
    // and front the newest one — the dock should show what the user just started.
    let cancelled = false
    void fetchDbFeatureMap(projectPath).then((rows) => {
      if (cancelled) return
      const st = useUiStore.getState()
      let sessions = st.activeFlowSessions
      for (const t of fresh) {
        const flowType = rows.get(t)?.flow || 'team'
        sessions = upsertSessionByTopic(sessions, `${flowType}/${t}`, {
          flowKey: `${flowType}.flow.yaml`,
          topic: t,
          isRunning: live.has(t),
          isPaused: false,
          isCli: false,
        })
      }
      st.setActiveFlowSessions(() => sessions)
      const newest = [...fresh].sort((a, b) => (live.get(b) ?? 0) - (live.get(a) ?? 0))[0]
      const newestFlow = rows.get(newest)?.flow || 'team'
      st.setActiveMonitorTab(`${newestFlow}/${newest}`)
    })
    return () => {
      cancelled = true
    }
  }, [engines, queued, projectPath])
}
