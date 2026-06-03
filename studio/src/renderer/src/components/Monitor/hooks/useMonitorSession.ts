import { useEffect, useRef } from 'react'
import { useStore } from '../../../store'
import { usePlanFiles } from '../../../hooks/usePlanFiles'
import { watchStart, readFile, onWatchEvent } from '../../../services/pathlyApi'
import { getFlowYamlName, extractTopic } from '../utils'
import type { FsmEvent } from '../../../types/index'

export function useMonitorSession(): { effectiveTopic: string | null; showTabBar: boolean } {
  const {
    projectPath,
    activeTopic,
    events,
    monitorSource,
    setMonitorSource,
    setFsmState,
    setEvents,
    setPipelineStates,
    activeFlowSessions,
    activeMonitorTab,
    setActiveFlowSessions,
    setActiveMonitorTab,
  } = useStore()

  const { planFolders } = usePlanFiles()

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

  // Proactive scan: read STATE.json for every plan folder and register any non-terminal flow as a session.
  useEffect(() => {
    if (!projectPath || planFolders.length === 0) return
    void Promise.all(
      planFolders.map(async (folder) => {
        try {
          const content = await readFile(`${folder.path}/STATE.json`)
          if (!content) return null
          const state = JSON.parse(content) as Record<string, unknown>
          const current = state.current as string | undefined
          if (current === 'DONE' || current === 'IDLE' || !current) return null
          const flowType = (state.flow as string | undefined) ?? 'team'
          return { key: `${flowType}/${folder.name}`, flowType, topic: folder.name }
        } catch { return null }
      })
    ).then((results) => {
      const active = results.filter((r): r is NonNullable<typeof r> => r !== null)
      if (active.length === 0) return
      setActiveFlowSessions((prev) => {
        const next = { ...prev }
        for (const item of active) {
          if (!(item.key in next)) {
            next[item.key] = { flowKey: `${item.flowType}.flow.yaml`, topic: item.topic, isRunning: true, isPaused: false, isCli: false }
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
      return
    }

    if (!projectPath) {
      setMonitorSource('chokidar')
      return
    }

    const roots = [
      `${projectPath}/pathly/plans/${effectiveTopic}`,
      `${projectPath}/pathly/debugs/${effectiveTopic}`,
      `${projectPath}/pathly/explorations/${effectiveTopic}`,
    ]

    Promise.any(
      roots.map((r) => readFile(`${r}/STATE.json`).then((c) => ({ base: r, content: c })))
    ).then(({ base, content }) => {
      if (!content) return
      try {
        const parsedState = JSON.parse(content)
        if (!parsedState.flow) {
          if (base.includes('/pathly/debugs/')) parsedState.flow = 'debug'
          else if (base.includes('/pathly/explorations/')) parsedState.flow = 'explore'
          else parsedState.flow = 'team'
        }
        if (!parsedState.feature && effectiveTopic) {
          parsedState.feature = effectiveTopic
        }
        setFsmState(parsedState)

        if (effectiveTopic) {
          const flowType = (parsedState.flow as string | undefined) ?? 'team'
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
            setActiveFlowSessions((prev) => ({
              ...prev,
              [sessionKey]: {
                flowKey: `${flowType}.flow.yaml`,
                topic: effectiveTopic,
                isRunning: true,
                isPaused: false,
                isCli: false as const
              }
            }))
          }
        }

        const flowName = parsedState.flow as string | undefined
        if (!flowName) return
        const yamlName = getFlowYamlName(flowName)
        readFile(`${projectPath}/src/pathly_data/core/flows/${yamlName}`)
          .then((yaml) => {
            if (!yaml) return
            const cleanYaml = yaml.replace(/\r/g, '')
            const match = cleanYaml.match(/states:\s*\n((?:[ \t]+-[ \t]+\S+\n?)+)/)
            if (match) {
              const states = match[1]
                .trim()
                .split('\n')
                .map((l) => l.replace(/^[ \t]+-[ \t]+/, '').trim().toUpperCase())
                .filter(Boolean)
              setPipelineStates(states)
            }
          })
          .catch(() => { /* flow YAML missing — FsmView uses fallback */ })

        readFile(`${base}/EVENTS.jsonl`).then((evContent) => {
          if (!evContent) return
          const parsed2: FsmEvent[] = []
          for (const line of evContent.split('\n')) {
            const trimmed = line.trim()
            if (!trimmed) continue
            try { parsed2.push(JSON.parse(trimmed) as FsmEvent) } catch { /* skip */ }
          }
          setEvents(parsed2)
        }).catch(() => { /* file may not exist yet */ })
      } catch { /* ignore malformed */ }
    }).catch(() => { /* topic not found in any root */ })

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
      if (data.path.endsWith('EVENTS.jsonl') && monitorSourceRef.current === 'chokidar') {
        const parsed: FsmEvent[] = []
        for (const line of data.content.split('\n')) {
          const trimmed = line.trim()
          if (trimmed) try { parsed.push(JSON.parse(trimmed) as FsmEvent) } catch { /* skip */ }
        }
        setEvents(parsed)
      }
    })

    const port = 8765
    const params = new URLSearchParams({ topic: effectiveTopic, project_root: projectPath })
    const es = new EventSource(`http://127.0.0.1:${port}/events/stream?${params}`)

    es.onopen = () => setMonitorSource('sse')

    es.onmessage = (ev) => {
      try {
        const event = JSON.parse(ev.data) as FsmEvent
        if (event.type === 'connected') return
        setEvents([...eventsRef.current, event])
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
  }, [effectiveTopic, projectPath, setMonitorSource, setFsmState, setEvents, setPipelineStates, setActiveFlowSessions, activeTopic, setActiveMonitorTab])

  return { effectiveTopic, showTabBar }
}
