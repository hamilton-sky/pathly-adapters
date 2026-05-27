import { useEffect, useRef, useState } from 'react'
import { MessageSquare } from 'lucide-react'
import { useChatStore } from '../../store/chatStore'
import { useTheme } from '../../useTheme'
import { ThinkingBlock } from './ThinkingBlock'
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

function ThinkingDots({ color }: { color: string }): JSX.Element {
  return (
    <span className={styles.thinking} aria-label="Thinking…">
      <span className={styles.dot} style={{ background: color }} />
      <span className={styles.dot} style={{ background: color }} />
      <span className={styles.dot} style={{ background: color }} />
    </span>
  )
}

export function MessageList(): JSX.Element {
  const messages = useChatStore((s) => s.messages)
  const t = useTheme()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (messages.length === 0) {
    return (
      <div
        className={styles.empty}
        style={{ color: t.textMuted, fontFamily: t.fontFamilyBase }}
      >
        <MessageSquare size={22} style={{ opacity: 0.4 }} />
        <span className={styles.emptyText}>Ask Conductor anything about your Pathly workflow.</span>
      </div>
    )
  }

  return (
    <div className={styles.list}>
      {messages.map((msg) => (
        <div key={msg.id} className={styles.message}>
          <span
            className={styles.badge}
            style={{
              background: msg.role === 'user' ? t.bgSurface1 : t.accent + '22',
              color: msg.role === 'user' ? t.textSecondary : t.accent,
              fontFamily: t.fontFamilyBase,
            }}
          >
            {msg.role === 'user' ? 'You' : 'Conductor'}
          </span>
          {msg.role === 'assistant' && msg.thinking && (
            <ThinkingBlock thinking={msg.thinking} status={msg.status} />
          )}
          {msg.role === 'assistant' && msg.status === 'streaming' && !msg.content && !msg.thinking
            ? <><ThinkingDots color={t.accent} /><StreamingTimer status={msg.status} /></>
            : msg.content
              ? (
                <span
                  className={styles.content}
                  style={{ color: t.textPrimary, fontFamily: t.fontFamilyBase }}
                >
                  {msg.content}
                </span>
              )
              : null
          }
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
