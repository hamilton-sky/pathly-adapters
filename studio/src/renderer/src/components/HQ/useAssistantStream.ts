import { useRef } from 'react'
import { useChatStore } from '../../store/chatStore'
import type { Message } from '../../store/chatStore'
import { splitThinkingContent } from '../../lib/thinkingParser'

/** Streams a model reply into its chat message, throttled to one store update
 *  per 60ms and split into thinking + content. Extracted from useHQ.
 *
 *  beginStream(id) pins the target message: writes go to THAT id, so a reply
 *  still arriving after New chat / opening another chat (an aborted model sends
 *  its partial text on the way out) can never land in a different conversation.
 *  Without a pinned id it falls back to the last message (older callers). */
export function useAssistantStream() {
  const streamTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const streamPending = useRef<ReturnType<typeof splitThinkingContent> | null>(null)
  const targetId = useRef<string | null>(null)

  function write(patch: Partial<Message>): void {
    const { updateMessage, updateLastMessage } = useChatStore.getState()
    if (targetId.current) updateMessage(targetId.current, patch)
    else updateLastMessage(patch)
  }

  /** Drop any queued update (Stop, or the final write is about to land). */
  function cancelStream(): void {
    if (streamTimer.current) {
      clearTimeout(streamTimer.current)
      streamTimer.current = null
    }
    streamPending.current = null
  }

  function beginStream(messageId: string): void {
    cancelStream()
    targetId.current = messageId
  }

  function queueAssistantStream(fullText: string): void {
    streamPending.current = splitThinkingContent(fullText)
    if (streamTimer.current) return
    streamTimer.current = setTimeout(() => {
      const pending = streamPending.current
      streamTimer.current = null
      streamPending.current = null
      if (pending) write({ content: pending.content, thinking: pending.thinking, status: 'streaming' })
    }, 60)
  }

  function finishAssistantStream(fullText: string, fallback: string): void {
    cancelStream()
    const { thinking, content } = splitThinkingContent(fullText)
    write({ content: content || fallback, thinking, status: 'done' })
  }

  return { beginStream, queueAssistantStream, finishAssistantStream, cancelStream }
}
