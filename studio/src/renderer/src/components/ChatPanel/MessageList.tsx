import { useEffect, useRef } from 'react'
import { MessageSquare } from 'lucide-react'
import { useChatStore } from '../../store/chatStore'
import { useTheme } from '../../useTheme'
import styles from './MessageList.module.css'

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
          <span
            className={styles.content}
            style={{ color: t.textPrimary, fontFamily: t.fontFamilyBase }}
          >
            {msg.content}
          </span>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
