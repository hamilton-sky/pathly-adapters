import { useEffect, useRef, useState } from 'react'
import { MessageSquare } from 'lucide-react'
import { useChatStore } from '../../../store/chatStore'
import { ThinkingBlock } from '../ThinkingBlock/ThinkingBlock'
import { ContextManifest, ContextUnavailableNote } from '../ContextManifest/ContextManifest'
import { ActionCards } from '../ActionCards/ActionCards'
import { BOARD_CONTEXT_UNAVAILABLE_MARKER, stripUnavailableMarker } from '../ContextManifest/manifestUtils'
import { renderSafeMarkdown } from '../../../lib/safeMarkdown'
import styles from './MessageList.module.css'

function StreamingTimer({ status }: { status: string }): JSX.Element | null {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    if (status !== 'streaming') return
    setElapsed(0)
    const id = setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [status])
  if (status !== 'streaming' || elapsed === 0) return null
  const mins = Math.floor(elapsed / 60)
  const secs = elapsed % 60
  const label = mins > 0 ? `${mins}:${String(secs).padStart(2, '0')}` : `${secs}s`
  return <span className={styles.timer}>{label}</span>
}

function ThinkingDots(): JSX.Element {
  return (
    <span className={styles.thinking} aria-label="Thinking…">
      <span className={styles.dot} />
      <span className={styles.dot} />
      <span className={styles.dot} />
    </span>
  )
}

export function MessageList(): JSX.Element {
  const messages = useChatStore((s) => s.messages)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Only the latest answer's context line links to the next-question choice.
  const latestManifestId = [...messages].reverse().find((m) => m.contextManifest)?.id

  if (messages.length === 0) {
    return (
      <div className={styles.empty}>
        <MessageSquare size={22} className={styles.emptyIcon} />
        <span className={styles.emptyText}>Ask anything about your Pathly workflow.</span>
      </div>
    )
  }

  return (
    <div className={styles.list}>
      {messages.map((msg) => (
        <div key={msg.id} className={styles.message}>
          <div className={styles.badgeRow}>
            <span className={`${styles.badge} ${msg.role === 'user' ? styles.badgeUser : styles.badgeAssistant}`}>
              {msg.role === 'user' ? 'You' : 'Conductor'}
            </span>
            {msg.role === 'assistant' && (msg as { source?: string }).source === 'claude-code' && (
              <span className={styles.ccTag}>CC</span>
            )}
          </div>
          {msg.role === 'assistant' && msg.thinking && (
            <ThinkingBlock thinking={msg.thinking} status={msg.status} />
          )}
          {msg.role === 'assistant' && msg.status === 'streaming' && !msg.content && !msg.thinking
            ? <><ThinkingDots /><StreamingTimer status={msg.status} /></>
            : msg.content
              ? msg.role === 'assistant'
                // Answers are Markdown from a model fed untrusted board text — rendered
                // through the escaping renderer, never raw marked().
                ? <div className={styles.markdown} dangerouslySetInnerHTML={{ __html: renderSafeMarkdown(stripUnavailableMarker(msg.content)) }} />
                : <span className={styles.content}>{stripUnavailableMarker(msg.content)}</span>
              : null
          }
          {/* HQ operator: the actions this answer proposed, each run only on its Run click. */}
          {msg.role === 'assistant' && msg.actionCards && msg.actionCards.length > 0 && (
            <ActionCards messageId={msg.id} cards={msg.actionCards} />
          )}
          {/* HQ context manifest: collapsible read-only line under local-model answers. */}
          {msg.role === 'assistant' && msg.contextManifest && (
            <ContextManifest manifest={msg.contextManifest} latest={msg.id === latestManifestId} />
          )}
          {/* The server's [board context unavailable] marker renders as a visible amber note. */}
          {msg.role === 'assistant'
            && msg.content.includes(BOARD_CONTEXT_UNAVAILABLE_MARKER)
            && !(msg.contextManifest && msg.contextManifest.unavailable) && (
            <ContextUnavailableNote />
          )}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
