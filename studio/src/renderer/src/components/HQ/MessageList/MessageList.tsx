import { useEffect, useRef, useState } from 'react'
import { useChatStore } from '../../../store/chatStore'
import { useUiStore } from '../../../store/uiStore'
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

const HINTS: Record<string, { label: string; prompts: string[] }> = {
  'skill-notebook': {
    label: 'Skill Notebook',
    prompts: [
      'What fragments are available for this skill?',
      'How do I add a review step to this skill?',
      'Explain what this skill does',
    ],
  },
  flow: {
    label: 'Canvas',
    prompts: [
      'What is the current pipeline state?',
      'How do I add a new stage?',
      'Show me the next action for this feature',
    ],
  },
  monitor: {
    label: 'Monitor',
    prompts: [
      'Why did the last run fail?',
      'How long did the last build take?',
      'What was the cost of the last run?',
    ],
  },
  default: {
    label: 'Pathly',
    prompts: [
      '/pathly go — continue the current feature',
      '/pathly build — run the next conversation',
      '/pathly status — show all active features',
    ],
  },
}

export function MessageList(): JSX.Element {
  const messages = useChatStore((s) => s.messages)
  const activePanel = useUiStore((s) => s.activePanel)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (messages.length === 0) {
    const hint = HINTS[activePanel] ?? HINTS.default
    return (
      <div className={styles.empty}>
        <span className={styles.emptyLabel}>{hint.label}</span>
        <ul className={styles.emptyPrompts}>
          {hint.prompts.map((p) => (
            <li key={p} className={styles.emptyPrompt}>{p}</li>
          ))}
        </ul>
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
              ? <span className={styles.content}>{msg.content}</span>
              : null
          }
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
