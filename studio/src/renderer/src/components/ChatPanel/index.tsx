import { useState, useEffect, useRef } from 'react'
import { useChatStore } from '../../store/chatStore'
import { useTerminalStore } from '../../store/terminalStore'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import { writeToTerminal } from '../../lib/launchTerminal'
import { buildPathlyContext } from '../../lib/pathlyContext'
import { ConductorHeader } from './ConductorHeader'
import { SkillsPanel } from './SkillsPanel'
import { MessageList } from './MessageList'
import { ChatInput } from './ChatInput'
import { MatchCard } from './MatchCard'
import { OutputSnippet } from './OutputSnippet'
import styles from './index.module.css'

function stripAnsi(raw: string): string {
  return raw
    // OSC sequences: ESC ] ... BEL or ST
    .replace(/\x1b\][\s\S]*?(?:\x07|\x1b\\)/g, '')
    // DCS / SOS / PM / APC: ESC [P X ^ _] ... ST
    .replace(/\x1b[PX^_][\s\S]*?\x1b\\/g, '')
    // CSI sequences: ESC [ params final-byte (0x40–0x7e)
    .replace(/\x1b\[[\x20-\x3f]*[\x40-\x7e]/g, '')
    // Any remaining ESC + one char
    .replace(/\x1b./g, '')
    // C0 control chars except CR (\r), LF (\n), TAB (\t)
    .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, '')
    // Private Use Area Unicode (icon glyphs that show as □)
    .replace(/[-]/g, '')
    // Lone carriage returns (without following newline)
    .replace(/\r(?!\n)/g, '')
}

export function ChatPanel(): JSX.Element {
  const [inputValue, setInputValue] = useState('')

  const messages = useChatStore((s) => s.messages)
  const addMessage = useChatStore((s) => s.addMessage)
  const updateLastMessage = useChatStore((s) => s.updateLastMessage)
  const currentMatch = useChatStore((s) => s.currentMatch)
  const outputLines = useChatStore((s) => s.outputLines)
  const targetKind = useChatStore((s) => s.targetKind)
  const appendOutputLine = useChatStore((s) => s.appendOutputLine)
  const clearOutputLines = useChatStore((s) => s.clearOutputLines)
  const setCurrentMatch = useChatStore((s) => s.setCurrentMatch)
  const setLoading = useChatStore((s) => s.setLoading)
  const isLoading = useChatStore((s) => s.isLoading)
  const isCommandRunning = useChatStore((s) => s.isCommandRunning)
  const setCommandRunning = useChatStore((s) => s.setCommandRunning)

  const tabs = useTerminalStore((s) => s.tabs)
  const addTab = useTerminalStore((s) => s.addTab)
  const open = useTerminalStore((s) => s.open)
  const toggle = useTerminalStore((s) => s.toggle)

  const projectPath = useStore((s) => s.projectPath)

  const t = useTheme()
  // Accumulates partial terminal data until a newline arrives
  const terminalBuffer = useRef('')

  // Only capture PTY output while a /pathly command is actively running
  useEffect(() => {
    const matchingTab = tabs.find((tab) => tab.kind === targetKind)
    if (!matchingTab) return

    const tabId = matchingTab.id
    const unsub = window.pathly?.terminal?.onData(tabId, (data) => {
      if (!useChatStore.getState().isCommandRunning) return

      terminalBuffer.current += stripAnsi(data)

      // Flush complete lines; keep the trailing partial in the buffer
      const parts = terminalBuffer.current.split('\n')
      terminalBuffer.current = parts.pop() ?? ''
      for (const line of parts) {
        const trimmed = line.replace(/\r/g, '').trim()
        if (trimmed.length > 0) appendOutputLine(trimmed)
      }
    })
    return () => {
      terminalBuffer.current = ''
      unsub?.()
    }
  }, [targetKind, tabs, appendOutputLine])

  async function handleSend(): Promise<void> {
    const text = inputValue.trim()
    if (!text) return

    // Stop any previous command capture when starting a new message
    setCommandRunning(false)
    clearOutputLines()

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
    } else {
      const context = await buildPathlyContext()
      const assistantMsg = {
        id: crypto.randomUUID(),
        role: 'assistant' as const,
        content: '',
        status: 'streaming' as const,
      }
      addMessage(assistantMsg)
      setLoading(true)

      try {
        const res = await fetch('http://127.0.0.1:8765/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: text,
            context,
            history: messages.map((m) => ({ role: m.role, content: m.content })),
          }),
        })

        const reader = res.body?.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let accContent = ''

        while (reader) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const payload = JSON.parse(line.slice(6)) as { text?: string; error?: string }
              if (payload.text) {
                accContent += payload.text
                updateLastMessage({ content: accContent })
              } else if (payload.error) {
                updateLastMessage({ content: payload.error, status: 'done' })
              }
            } catch { /* malformed SSE chunk — skip */ }
          }
        }
        updateLastMessage({ status: 'done' })
      } catch {
        updateLastMessage({ content: 'Chat server unavailable.', status: 'done' })
      } finally {
        setLoading(false)
      }
    }
  }

  function handleSkillClick(command: string): void {
    setInputValue(command)
  }

  async function handleRun(): Promise<void> {
    if (!currentMatch) return
    clearOutputLines()
    setCommandRunning(true)
    await writeToTerminal(targetKind, currentMatch.command, projectPath, tabs, addTab, open, toggle)
  }

  function handleReject(): void {
    setCurrentMatch(null)
    setCommandRunning(false)
    clearOutputLines()
  }

  function handleSelectAlt(skill: string): void {
    setCurrentMatch({ skill, confidence: 1.0, command: `/pathly ${skill}` })
    setCommandRunning(false)
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
      {isCommandRunning && outputLines.length > 0 && (
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
        disabled={isLoading}
      />
    </div>
  )
}
