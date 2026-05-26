import { useState } from 'react'
import { useChatStore } from '../../store/chatStore'
import { useTheme } from '../../useTheme'
import { ConductorHeader } from './ConductorHeader'
import { SkillsPanel } from './SkillsPanel'
import { MessageList } from './MessageList'
import { ChatInput } from './ChatInput'
import styles from './index.module.css'

export function ChatPanel(): JSX.Element {
  const [inputValue, setInputValue] = useState('')
  const addMessage = useChatStore((s) => s.addMessage)
  const t = useTheme()

  function handleSend(): void {
    const text = inputValue.trim()
    if (!text) return

    const userMsg = {
      id: crypto.randomUUID(),
      role: 'user' as const,
      content: text,
      status: 'done' as const,
    }
    addMessage(userMsg)
    setInputValue('')

    const assistantMsg = {
      id: crypto.randomUUID(),
      role: 'assistant' as const,
      content: 'Conductor coming in Conv 9...',
      status: 'done' as const,
    }
    addMessage(assistantMsg)
  }

  function handleSkillClick(command: string): void {
    setInputValue(command)
  }

  return (
    <div
      className={styles.panel}
      style={{ background: t.bgBase, borderLeft: t.border, fontFamily: t.fontFamilyBase }}
    >
      <ConductorHeader />
      <SkillsPanel onSkillClick={handleSkillClick} />
      <MessageList />
      <ChatInput
        value={inputValue}
        onChange={setInputValue}
        onSend={handleSend}
      />
    </div>
  )
}
