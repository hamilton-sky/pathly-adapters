import { useState, useEffect } from 'react'
import { useChatStore } from '../../store/chatStore'
import { useTerminalStore } from '../../store/terminalStore'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import { writeToTerminal } from '../../lib/launchTerminal'
import { ConductorHeader } from './ConductorHeader'
import { SkillsPanel } from './SkillsPanel'
import { MessageList } from './MessageList'
import { ChatInput } from './ChatInput'
import { MatchCard } from './MatchCard'
import { OutputSnippet } from './OutputSnippet'
import styles from './index.module.css'

function stripAnsi(data: string): string {
  return data
    .replace(/\x1b\[[0-9;]*m/g, '')
    .replace(/\x1b\[[0-9;]*[A-Za-z]/g, '')
}

export function ChatPanel(): JSX.Element {
  const [inputValue, setInputValue] = useState('')

  const addMessage = useChatStore((s) => s.addMessage)
  const currentMatch = useChatStore((s) => s.currentMatch)
  const outputLines = useChatStore((s) => s.outputLines)
  const targetKind = useChatStore((s) => s.targetKind)
  const appendOutputLine = useChatStore((s) => s.appendOutputLine)
  const clearOutputLines = useChatStore((s) => s.clearOutputLines)
  const setCurrentMatch = useChatStore((s) => s.setCurrentMatch)
  const isLoading = useChatStore((s) => s.isLoading)

  const tabs = useTerminalStore((s) => s.tabs)
  const addTab = useTerminalStore((s) => s.addTab)
  const open = useTerminalStore((s) => s.open)
  const toggle = useTerminalStore((s) => s.toggle)

  const projectPath = useStore((s) => s.projectPath)

  const t = useTheme()

  useEffect(() => {
    const matchingTab = tabs.find((tab) => tab.kind === targetKind)
    if (!matchingTab) return

    const tabId = matchingTab.id
    const unsub = window.pathly.terminal.onData(tabId, (data) => {
      appendOutputLine(stripAnsi(data))
    })
    return unsub
  }, [targetKind, tabs, appendOutputLine])

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

    if (text.startsWith('/pathly')) {
      const parts = text.split(' ')
      const skill = parts[1] || ''
      setCurrentMatch({ skill, confidence: 1.0, command: text })
      clearOutputLines()
    } else {
      const assistantMsg = {
        id: crypto.randomUUID(),
        role: 'assistant' as const,
        content: 'Conductor coming in Conv 9...',
        status: 'done' as const,
      }
      addMessage(assistantMsg)
    }
  }

  function handleSkillClick(command: string): void {
    setInputValue(command)
  }

  async function handleRun(): Promise<void> {
    if (!currentMatch) return
    await writeToTerminal(targetKind, currentMatch.command, projectPath, tabs, addTab, open, toggle)
    clearOutputLines()
  }

  function handleReject(): void {
    setCurrentMatch(null)
    clearOutputLines()
  }

  function handleSelectAlt(skill: string): void {
    setCurrentMatch({ skill, confidence: 1.0, command: `/pathly ${skill}` })
    clearOutputLines()
  }

  const outputStatus = isLoading ? 'running' : 'done'

  return (
    <div
      className={styles.panel}
      style={{ background: t.bgBase, borderLeft: t.border, fontFamily: t.fontFamilyBase }}
    >
      <ConductorHeader />
      <SkillsPanel onSkillClick={handleSkillClick} />
      <MessageList />
      {currentMatch !== null && (
        <MatchCard
          match={currentMatch}
          alts={[]}
          onRun={() => { void handleRun() }}
          onReject={handleReject}
          onSelectAlt={handleSelectAlt}
        />
      )}
      {outputLines.length > 0 && (
        <OutputSnippet
          target={targetKind === 'claude' ? 'claude-code' : 'codex'}
          status={outputStatus}
          lines={outputLines}
        />
      )}
      <ChatInput
        value={inputValue}
        onChange={setInputValue}
        onSend={handleSend}
      />
    </div>
  )
}
