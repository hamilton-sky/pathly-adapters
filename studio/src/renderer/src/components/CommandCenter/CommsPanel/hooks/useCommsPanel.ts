import { useCallback, useEffect, useRef, useState } from 'react'
import type { BoardScope, Message, MessageType } from '../../types'
import { useCommsStore } from '../../../../store/commsStore'
import { scopeToParams } from '../../../../store/commsApi'
import { useProjectStore } from '../../../../store/projectStore'
import { useToastStore } from '../../../../store/toastStore'
import { PATHLY_API_BASE } from '../../../../lib/config'
import { handleSummaryRequest } from '../ArtifactsView/handleSummaryRequest'

// Per-section binding: messages for one board scope + send/answer/resolve handlers
// + a one-shot flash for freshly-posted messages.
// Owns board load on mount/change and SSE subscription (GET /events/comms?scope=).
export function useCommsPanel(scope: BoardScope, mainFeature: string) {
  const store = useCommsStore()
  const projectPath = useProjectStore((s) => s.projectPath)
  const [flashId, setFlashId] = useState<string | null>(null)

  const key = scope === 'feature' ? mainFeature : scope
  const messages = store.messagesFor(scope, mainFeature)
  const feature = store.features.find((f) => f.id === mainFeature)
  const pendingCount = store.pendingCount(mainFeature)

  const projectRoot = projectPath.replace(/\\/g, '/').replace(/\/$/, '')

  // Stable ref so the SSE handler always calls the current loadBoard without
  // re-creating the EventSource on every render.
  const loadRef = useRef<() => void>(() => { /* noop until effect runs */ })
  loadRef.current = () => { void store.loadBoard(scope, key, projectRoot) }

  // Board load + SSE subscription
  useEffect(() => {
    if (!key) return

    void store.loadBoard(scope, key, projectRoot)

    // Subscribe to the SAME scope the server broadcasts under — the canonical DB
    // scope from scopeToParams, NOT the raw key. For feature/global these are equal,
    // but a project board is stored under the normalized project path, so subscribing
    // to 'project' (the key) would never receive its COMMS_UPDATE events.
    const sseScope = scopeToParams(scope, scope === 'project' ? projectRoot : key).scope

    let es: EventSource | null = null
    try {
      es = new EventSource(`${PATHLY_API_BASE}/events/comms?scope=${encodeURIComponent(sseScope)}`)
      es.onmessage = (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data as string) as { type: string; event?: string; phase?: string; goal_id?: string; message_id?: string; error?: string; artifact_id?: string; artifact_path?: string; text?: string; reason?: string; selection?: { type?: string; id?: string } }
          if (data.type === 'COMMS_UPDATE') {
            // Server-initiated summary handoff (Conv 4): the server emits this
            // instead of running inference. Run the resolved target client-side and
            // POST the result back. Best-effort — handleSummaryRequest never throws.
            if (data.event === 'summary_request') {
              void handleSummaryRequest({
                artifact_id: data.artifact_id,
                artifact_path: data.artifact_path,
                selection: data.selection,
              })
              return
            }
            // Drive the agent control's run state from the run lifecycle so it stays
            // green (and Stop stays enabled) until the agent actually finishes.
            if (data.event === 'board_run' && data.phase) {
              useCommsStore.getState().markBoardRunPhase(key, data.phase)
            }
            if ((data.event === 'goal_run' || data.event === 'goal_decompose')
                && data.phase && data.goal_id) {
              useCommsStore.getState().markGoalRunPhase(data.goal_id, data.phase)
            }
            // Offline summarizer lifecycle → per-artifact badge + toast on done/fail.
            if (data.message_id && (data.event === 'summarizing'
                || data.event === 'summary_ready' || data.event === 'summary_failed')) {
              const st = data.event === 'summarizing' ? 'summarizing'
                : data.event === 'summary_ready' ? 'ready' : 'failed'
              useCommsStore.getState().markSummaryStatus(data.message_id, st, data.error)
            }
            // Loop/DAG task progress → toast on each task completion. The supervisor emits
            // task_done / task_failed (with the task text) as it drains the DAG, so these fire
            // regardless of whether the per-task agent posted its own status.
            if (data.event === 'task_done' || data.event === 'task_failed') {
              const label = (data.text || 'task').slice(0, 70)
              if (data.event === 'task_done') {
                useToastStore.getState().push(`${label}`, 'success', { category: 'agent_done' })
              } else {
                const why = data.reason ? ` — ${data.reason.slice(0, 60)}` : ''
                useToastStore.getState().push(`${label}${why}`, 'error', { category: 'agent_done' })
              }
            }
            loadRef.current()
          }
        } catch { /* ignore parse errors */ }
      }
      es.onerror = () => { /* EventSource auto-reconnects */ }
    } catch { /* EventSource not available — silently skip */ }

    // Fallback poll. The SSE push can silently stall — most commonly the browser's
    // ~6-concurrent-connection HTTP/1.1 cap, hit once several EventSource streams are
    // open (per-board + spawn + menu + runner) — which leaves the board stale until
    // remount. A light periodic reload keeps it live regardless: instant when the SSE
    // delivers, ≤5s behind when it doesn't. GET /comms is a small loopback read.
    const poll = window.setInterval(() => { loadRef.current() }, 5000)

    return () => { es?.close(); window.clearInterval(poll) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, key, projectRoot])

  const flash = (id: string) => {
    setFlashId(id)
    window.setTimeout(() => setFlashId(null), 900)
  }

  const post = useCallback(
    (type: MessageType, text: string) => {
      const id = store.post(key, type, text, scope === 'feature' ? feature?.stage : null)
      flash(id)
    },
    [store, key, scope, feature],
  )

  const answer = useCallback(
    (mid: string, opt: string) => store.answer(mainFeature, mid, opt),
    [store, mainFeature],
  )

  const resolve = useCallback(
    (mid: string, mode: 'block' | 'note' | 'ignore') => { void store.resolve(key, mid, mode) },
    [store, key],
  )

  const toggleScope = useCallback(
    (sc: BoardScope) => store.toggleScope(mainFeature, sc, projectRoot),
    [store, mainFeature, projectRoot],
  )

  const del = useCallback(
    (mid: string) => store.deleteMessage(key, mid),
    [store, key],
  )

  const editMessage = useCallback(
    (mid: string, text: string) => store.editMessage(key, mid, text),
    [store, key],
  )

  const supersede = useCallback(
    (oldId: string, newId: string) => store.supersede(key, oldId, newId),
    [store, key],
  )

  const attach = useCallback(
    (mid: string, path: string, atype?: Message['atype']) => store.attach(key, mid, path, atype),
    [store, key],
  )

  const runSingleAgent = useCallback(
    (opts: { agent?: string; skill?: string; systemPrompt?: string; interactive?: boolean; adapter?: string; instructions?: string; progress?: string }) =>
      store.runSingleAgent(key, opts),
    [store, key],
  )

  const runGoal = useCallback(
    (goal_id: string, executor?: string, opts?: { adapter?: string; model?: string }) =>
      store.runGoal(goal_id, executor, opts),
    [store],
  )

  const stopGoal = useCallback(
    (goal_id: string) => store.stopGoal(goal_id),
    [store],
  )

  const searchResults = store.searchResults
  const searchTerm = store.searchTerm
  const runSearch = useCallback((q: string) => { void store.runSearch(key, q) }, [store, key])
  const clearSearch = useCallback(() => store.clearSearch(), [store])

  const reload = useCallback(() => { void store.loadBoard(scope, key, projectRoot) }, [store, scope, key, projectRoot])

  return {
    messages, feature, pendingCount, flashId, post, answer, resolve,
    toggleScope, del, editMessage, supersede, attach, runSingleAgent, runGoal, stopGoal,
    searchResults, searchTerm, runSearch, clearSearch, reload,
  }
}
