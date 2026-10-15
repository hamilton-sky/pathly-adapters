import { useEffect, useRef } from 'react'
import { useChatStore } from '../../store/chatStore'
import { useHqHistoryStore } from '../../store/hqHistoryStore'
import { restorable } from '../../store/hqHistory'

/** HQ chat history, one per project: autosaves the open chat under its project,
 *  reopens it after a reload, swaps the chat when the user switches projects,
 *  and backs the header's New chat button and history list.
 *  `stop` aborts an answer still being generated (so its text cannot land in
 *  another chat); `reset` clears the panel. */
export function useHqHistory({ project, stop, reset }: { project: string; stop: () => void; reset: () => void }) {
  const history = useHqHistoryStore((s) => s.byProject[project])
  // The project the on-screen chat belongs to. Autosave keys off this, and it
  // only moves once the old project's chat has been saved.
  const projectRef = useRef(project)

  useEffect(() => {
    // Save once an answer settles, not on every streamed token.
    return useChatStore.subscribe((state, prev) => {
      if (state.messages === prev.messages) return
      if (state.messages.some((m) => m.status === 'streaming')) return
      useHqHistoryStore.getState().saveCurrent(projectRef.current, state.messages)
    })
  }, [])

  useEffect(() => {
    const store = useHqHistoryStore.getState()
    if (projectRef.current !== project) {
      // Switched projects: the old chat is already saved under the old project
      // (stop() settles an answer in flight, which saves it there too).
      if (useChatStore.getState().isLoading) stop()
      projectRef.current = project
      reset()
    }
    store.adoptUnassigned(project)
    const h = store.ensure(project)
    const current = h.sessions.find((s) => s.id === h.currentId)
    if (current && useChatStore.getState().messages.length === 0) {
      useChatStore.getState().setMessages(restorable(current.messages))
    }
    // stop/reset are re-created each render; the switch is keyed on project only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project])

  function newChat(): void {
    if (useChatStore.getState().isLoading) stop()
    useHqHistoryStore.getState().startNew(projectRef.current)
    reset()
  }

  function openChat(id: string): void {
    const h = useHqHistoryStore.getState().ensure(projectRef.current)
    if (id === h.currentId) return
    if (useChatStore.getState().isLoading) stop()
    const session = useHqHistoryStore.getState().open(projectRef.current, id)
    if (!session) return
    reset()
    useChatStore.getState().setMessages(restorable(session.messages))
  }

  const list = (history?.sessions ?? []).map((s) => ({
    id: s.id,
    title: s.title,
    messageCount: s.messages.length,
    lastActivity: new Date(s.updatedAt).toISOString(),
    current: s.id === history?.currentId,
  }))
  return { sessions: list, newChat, openChat }
}
