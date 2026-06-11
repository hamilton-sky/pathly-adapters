import { useCallback, useState } from 'react'
import type { BoardScope, MessageType } from '../../CommandCenter/types'
import { useCommsStore } from '../../../../store/commsStore'

// Per-section binding: messages for one board scope + send/answer/resolve handlers
// + a one-shot flash for freshly-posted messages.
// TODO: also owns SSE subscription (GET /events/comms?scope=) → store.appendMessage
export function useCommsPanel(scope: BoardScope, mainFeature: string) {
  const store = useCommsStore()
  const [flashId, setFlashId] = useState<string | null>(null)

  const key = scope === 'feature' ? mainFeature : scope
  const messages = store.messagesFor(scope, mainFeature)
  const feature = store.features.find((f) => f.id === mainFeature)
  const pendingCount = store.pendingCount(mainFeature)

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
    (mid: string, mode: 'block' | 'note' | 'ignore') => store.resolve(mid, mode),
    [store],
  )

  const toggleScope = useCallback(
    (s: BoardScope) => store.toggleScope(mainFeature, s),
    [store, mainFeature],
  )

  const del = useCallback(
    (mid: string) => store.deleteMessage(key, mid),
    [store, key],
  )

  return { messages, feature, pendingCount, flashId, post, answer, resolve, toggleScope, del }
}
