import { useCallback, useEffect, useRef } from 'react'
import { useStore } from '../../../store'
import { usePlanFiles } from '../../../hooks/usePlanFiles'
import { watchStart, readFile, onWatchEvent, fetchFlowGraph } from '../../../services/pathlyApi'
import { fetchDbFeatureMap } from '../../../store/commsApi'
import { getFlowYamlName, extractTopic, mergeBillingUpdate, parseFlowStages, parseFlowGraph, upsertSessionByTopic } from '../utils'
import { useLiveFlowSessions } from './useLiveFlowSessions'
import type { FsmEvent, FsmState } from '../../../types/index'

export function useMonitorSession(): { effectiveTopic: string | null; showTabBar: boolean; refresh: () => void } {
  const {
    projectPath,
    activeTopic,
    events,
    monitorSource,
    setMonitorSource,
    setFsmState,
    setEvents,
    setPipelineStates,
    setStageRoles,
    setStageSkills,
    activeFlowSessions,
    activeMonitorTab,
    setActiveFlowSessions,
    setActiveMonitorTab,
  } = useStore()

  const { planFolders } = usePlanFiles()

  // Live spawn-gate engines → sessions/tabs: every running flow (goal team runs included)
  // registers its tab and fronts it at spawn — the dock tracks what the user actually started.
  useLiveFlowSessions()

  const eventsRef = useRef(events)
  eventsRef.current = events

  const monitorSourceRef = useRef(monitorSource)
  monitorSourceRef.current = monitorSource

  const activeMonitorTabRef = useRef(activeMonitorTab)
  activeMonitorTabRef.current = activeMonitorTab

  const activeTabValid = activeMonitorTab != null && !!activeFlowSessions[activeMonitorTab]
  const effectiveTopic = activeTabValid ? extractTopic(activeMonitorTab!) : activeTopic
  const showTabBar = Object.keys(activeFlowSessions).length >= 1

  // Keep a ref so the auto-select effect can read current sessions without depending on them.
  const activeFlowSessionsRef = useRef(activeFlowSessions)
  activeFlowSessionsRef.current = activeFlowSessions

  // Clear stale session state whenever the active project changes.
  useEffect(() => {
    setActiveFlowSessions(() => ({}))
    setActiveMonitorTab(null)
    setFsmState(null)
    setEvents([])
  }, [projectPath, setActiveFlowSessions, setActiveMonitorTab, setFsmState, setEvents])

  // Proactive scan: look up every plan folder's DB-first feature row and register any
  // non-terminal flow as a session (state-one-authority — no STATE.json mirror read).
  // These are OPEN flows, not necessarily running ones — isRunning stays false until the
  // spawn gate reports a live engine for the topic (useLiveFlowSessions owns that bit).
  useEffect(() => {
    if (!projectPath || planFolders.length === 0) return
    void fetchDbFeatureMap(projectPath).then((dbFeatures) => {
      const active = planFolders.flatMap((folder) => {
        const row = dbFeatures.get(folder.name)
        if (!row) return []
        const current = row.state
        if (!current || current === 'UNKNOWN' || current === 'DONE' || current === 'IDLE') return []
        const flowType = row.flow || 'team'
        return [{ key: `${flowType}/${folder.name}`, flowType, topic: folder.name }]
      })
      if (active.length === 0) return
      setActiveFlowSessions((prev) => {
        const next = { ...prev }
        for (const item of active) {
          if (!(item.key in next)) {
            next[item.key] = { flowKey: `${item.flowType}.flow.yaml`, topic: item.topic, isRunning: false, isPaused: false, isCli: false }
          }
        }
        return next
      })
    })
  }, [projectPath, planFolders, setActiveFlowSessions])

  // When sidebar selection changes, auto-select the matching tab — but never override a tab the
  // user has already chosen. This prevents the tab from resetting when switching Canvas↔Monitor.
  useEffect(() => {
    if (!activeTopic) return
    const sessions = activeFlowSessionsRef.current
    // Skip if the current tab already points to a valid session (user's explicit choice)
    if (activeMonitorTabRef.current != null && !!sessions[activeMonitorTabRef.current]) return
    const matchingKey = Object.keys(sessions).find((k) => extractTopic(k) === activeTopic)
    if (matchingKey) setActiveMonitorTab(matchingKey)
  }, [activeTopic, setActiveMonitorTab])

  useEffect(() => {
    if (!effectiveTopic) {
      setPipelineStates([])
      setStageRoles({})
      setStageSkills({})
      return
    }

    if (!projectPath) {
      setMonitorSource('chokidar')
      return
    }

    // DB-first (state-one-authority): the /db/features row replaces the per-root
    // STATE.json probes — one call covers features/debugs/explorations plus the
    // server-side filesystem fallback for never-run features.
    fetchDbFeatureMap(projectPath).then((dbFeatures) => {
      const row = dbFeatures.get(effectiveTopic)
      if (!row) return
      const parsedState: FsmState = {
        current: row.state !== 'UNKNOWN' ? row.state : '',
        flow: row.flow || 'team',
        feature: row.feature,
        updated_at: row.updated_at,
      }
      setFsmState(parsedState)

      if (effectiveTopic) {
        const flowType = parsedState.flow ?? 'team'
        const sessionKey = `${flowType}/${effectiveTopic}`
        const isDone = parsedState.current === 'DONE' || parsedState.current === 'IDLE'
        if (isDone) {
          setActiveFlowSessions((prev) => {
            if (!(sessionKey in prev)) return prev
            const next = { ...prev }
            delete next[sessionKey]
            return next
          })
          if (activeMonitorTabRef.current === sessionKey) setActiveMonitorTab(null)
        } else {
          // Upsert under the DB row's REAL flow name, dropping any same-topic session that was
          // registered under a guessed flow (spawn-time 'team' default). isRunning is preserved
          // from whichever session held the topic — engine liveness is owned by the gate hook.
          setActiveFlowSessions((prev) => {
            const wasRunning = Object.entries(prev).some(
              ([k, s]) => extractTopic(k) === effectiveTopic && s.isRunning,
            )
            return upsertSessionByTopic(prev, sessionKey, {
              flowKey: `${flowType}.flow.yaml`,
              topic: effectiveTopic,
              isRunning: wasRunning,
              isPaused: false,
              isCli: false,
            })
          })
          if (
            activeMonitorTabRef.current &&
            activeMonitorTabRef.current !== sessionKey &&
            extractTopic(activeMonitorTabRef.current) === effectiveTopic
          ) {
            setActiveMonitorTab(sessionKey)
          }
        }
      }

      const flowName = parsedState.flow
      if (!flowName) return

      // Flows are DB-first at runtime (the FSM runs the DB copy; core/flows/*.yaml are
      // only a boot-time seed). Read the LIVE graph so user-created and user-edited flows
      // resolve their real per-stage roles/skills; fall back to the seed file only when
      // the server/DB is unavailable.
      fetchFlowGraph(flowName)
        .then((res) => {
          const dbParsed = res?.graph ? parseFlowGraph(res.graph) : null
          if (dbParsed) {
            setPipelineStates(dbParsed.states)
            setStageRoles(dbParsed.roles)
            setStageSkills(dbParsed.skills)
            return
          }
          return readFile(`${projectPath}/src/pathly_data/core/flows/${getFlowYamlName(flowName)}`)
            .then((yaml) => {
              if (!yaml) return
              const parsed = parseFlowStages(yaml.replace(/\r/g, ''))
              if (!parsed) return
              setPipelineStates(parsed.states)
              setStageRoles(parsed.roles)
              setStageSkills(parsed.skills)
            })
        })
        .catch(() => { /* neither DB nor seed available — FsmView uses default pipeline */ })

      const port = 8765
      const histParams = new URLSearchParams({ topic: effectiveTopic, project_root: projectPath })
      fetch(`http://127.0.0.1:${port}/events/history?${histParams}`)
        .then((r) => r.ok ? r.json() : [])
        .then((data: FsmEvent[]) => { if (data.length > 0) setEvents(data) })
        .catch(() => { /* server not yet running — SSE will stream events when it starts */ })
    })

    watchStart(projectPath, effectiveTopic)
    const removeListener = onWatchEvent((data) => {
      if (data.path.endsWith('STATE.json')) {
        try {
          const newState = JSON.parse(data.content)
          setFsmState(newState)
          if (newState.current === 'DONE' || newState.current === 'IDLE') {
            const flowType = (newState.flow as string | undefined) ?? 'team'
            const sessionKey = `${flowType}/${activeTopic}`
            setActiveFlowSessions((prev) => {
              if (!(sessionKey in prev)) return prev
              const next = { ...prev }
              delete next[sessionKey]
              return next
            })
            if (activeMonitorTabRef.current === sessionKey) setActiveMonitorTab(null)
          }
        } catch { /* ignore */ }
      }
      // EVENTS.jsonl is no longer written — events come from SSE or /events/history
    })

    const port = 8765
    const params = new URLSearchParams({ topic: effectiveTopic, project_root: projectPath })
    const es = new EventSource(`http://127.0.0.1:${port}/events/stream?${params}`)

    es.onopen = () => setMonitorSource('sse')

    es.onmessage = (ev) => {
      try {
        const event = JSON.parse(ev.data) as FsmEvent
        if (event.type === 'connected') return
        if (event.type === 'BILLING_UPDATE') {
          setEvents(mergeBillingUpdate(eventsRef.current, event))
        } else {
          setEvents([...eventsRef.current, event])
        }
      } catch { /* skip malformed */ }
    }

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) {
        setMonitorSource('chokidar')
      }
    }

    return () => {
      removeListener()
      es.close()
    }
  }, [effectiveTopic, projectPath, setMonitorSource, setFsmState, setEvents, setPipelineStates, setStageRoles, setStageSkills, setActiveFlowSessions, activeTopic, setActiveMonitorTab])

  const effectiveTopicRef = useRef(effectiveTopic)
  effectiveTopicRef.current = effectiveTopic
  const projectPathRef = useRef(projectPath)
  projectPathRef.current = projectPath

  const refresh = useCallback(() => {
    const topic = effectiveTopicRef.current
    const path = projectPathRef.current
    if (!topic || !path) return

    // DB-first (state-one-authority): fresh /db/features lookup, no STATE.json read.
    fetchDbFeatureMap(path, { fresh: true }).then((dbFeatures) => {
      const row = dbFeatures.get(topic)
      if (!row) return
      setFsmState({
        current: row.state !== 'UNKNOWN' ? row.state : '',
        flow: row.flow || 'team',
        feature: row.feature,
        updated_at: row.updated_at,
      })
    })

    const port = 8765
    const histParams = new URLSearchParams({ topic, project_root: path })
    fetch(`http://127.0.0.1:${port}/events/history?${histParams}`)
      .then((r) => r.ok ? r.json() : [])
      .then((data: FsmEvent[]) => { if (data.length > 0) setEvents(data) })
      .catch(() => { /* server not running */ })
  }, [setFsmState, setEvents])

  return { effectiveTopic, showTabBar, refresh }
}
