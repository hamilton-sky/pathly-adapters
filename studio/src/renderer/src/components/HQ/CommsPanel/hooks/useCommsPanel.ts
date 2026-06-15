import { useCallback, useEffect, useRef, useState } from 'react'
import type { BoardScope, Message, MessageType } from '../../../CommandCenter/types'
import { useCommsStore } from '../../../../store/commsStore'
import { useProjectStore } from '../../../../store/projectStore'
import { PATHLY_API_BASE } from '../../../../lib/config'

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

    let es: EventSource | null = null
    try {
      es = new EventSource(`${PATHLY_API_BASE}/events/comms?scope=${encodeURIComponent(key)}`)
      es.onmessage = (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data as string) as { type: string }
          if (data.type === 'COMMS_UPDATE') {
            loadRef.current()
          }
        } catch { /* ignore parse errors */ }
      }
      es.onerror = () => { /* EventSource auto-reconnects */ }
    } catch { /* EventSource not available — silently skip */ }

    return () => { es?.close() }
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

  const supersede = useCallback(
    (oldId: string, newId: string) => store.supersede(key, oldId, newId),
    [store, key],
  )

  const attach = useCallback(
    (mid: string, path: string, atype?: Message['atype']) => store.attach(key, mid, path, atype),
    [store, key],
  )

  const runSingleAgent = useCallback(
    (opts: { agent?: string; skill?: string; systemPrompt?: string; interactive?: boolean }) =>
      store.runSingleAgent(key, opts),
    [store, key],
  )

  const searchResults = store.searchResults
  const searchTerm = store.searchTerm
  const runSearch = useCallback((q: string) => { void store.runSearch(key, q) }, [store, key])
  const clearSearch = useCallback(() => store.clearSearch(), [store])

  return {
    messages, feature, pendingCount, flashId, post, answer, resolve,
    toggleScope, del, supersede, attach, runSingleAgent,
    searchResults, searchTerm, runSearch, clearSearch,
  }
}
