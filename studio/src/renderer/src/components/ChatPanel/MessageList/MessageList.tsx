import { useEffect, useRef, useState } from 'react'
import { MessageSquare } from 'lucide-react'
import { useChatStore } from '../../../store/chatStore'
import { ThinkingBlock } from '../ThinkingBlock/ThinkingBlock'
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

  if (messages.length === 0) {
    return (
      <div className={styles.empty}>
        <MessageSquare size={22} className={styles.emptyIcon} />
        <span className={styles.emptyText}>Ask Conductor anything about your Pathly workflow.</span>
      </div>
    )
  }

  return (
    <div className={styles.list}>
      {messages.map((msg) => (
        <div key={msg.id} className={styles.message}>
          <span className={`${styles.badge} ${msg.role === 'user' ? styles.badgeUser : styles.badgeAssistant}`}>
            {msg.role === 'user' ? 'You' : 'Conductor'}
          </span>
          {msg.role === 'assistant' && msg.thinking && (
            <ThinkingBlock thinking={msg.thinking} status={msg.status} />
          )}
          {msg.role === 'assistant' && msg.status === 'streaming' && !msg.content && !msg.thinking
            ? <><ThinkingDots /><StreamingTimer status={msg.status} /></>
            : msg.content
              ? <span className={styles.content}>{msg.content}</span>
              : null
          }
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
