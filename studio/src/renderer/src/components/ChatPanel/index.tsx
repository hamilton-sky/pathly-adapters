import { useState, useEffect, useRef } from 'react'
import { useChatStore } from '../../store/chatStore'
import { useTerminalStore } from '../../store/terminalStore'
import { useStore } from '../../store'
import { useUiStore } from '../../store/uiStore'
import { useTheme } from '../../useTheme'
import { writeToTerminal } from '../../lib/launchTerminal'
import { buildPathlyContext } from '../../lib/pathlyContext'
import { PATHLY_API_BASE } from '../../lib/config'
import { matchIntent, preEmbedSkills } from '../../lib/embedRouter'
import { loadSkills } from '../../lib/skillsManifest'
import { ConductorHeader } from './ConductorHeader'
import { SkillsPanel } from './SkillsPanel'
import { MessageList } from './MessageList'
import { ChatInput } from './ChatInput'
import { MatchCard } from './MatchCard'
import { OutputSnippet } from './OutputSnippet'
import { useChatResize } from './useChatResize'
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
  const { chatRef, onDragStart, width } = useChatResize()

  const messages = useChatStore((s) => s.messages)
  const addMessage = useChatStore((s) => s.addMessage)
  const updateLastMessage = useChatStore((s) => s.updateLastMessage)
  const currentMatch = useChatStore((s) => s.currentMatch)
  const altMatches = useChatStore((s) => s.altMatches)
  const outputLines = useChatStore((s) => s.outputLines)
  const targetKind = useChatStore((s) => s.targetKind)
  const autoApprove = useChatStore((s) => s.autoApprove)
  const appendOutputLine = useChatStore((s) => s.appendOutputLine)
  const clearOutputLines = useChatStore((s) => s.clearOutputLines)
  const clearMessages = useChatStore((s) => s.clearMessages)
  const setCurrentMatch = useChatStore((s) => s.setCurrentMatch)
  const setAltMatches = useChatStore((s) => s.setAltMatches)
  const setIsEmbedding = useChatStore((s) => s.setIsEmbedding)
  const setEmbedReady = useChatStore((s) => s.setEmbedReady)
  const setLoading = useChatStore((s) => s.setLoading)
  const isLoading = useChatStore((s) => s.isLoading)
  const isCommandRunning = useChatStore((s) => s.isCommandRunning)
  const setCommandRunning = useChatStore((s) => s.setCommandRunning)

  const tabs = useTerminalStore((s) => s.tabs)
  const addTab = useTerminalStore((s) => s.addTab)
  const open = useTerminalStore((s) => s.open)
  const toggle = useTerminalStore((s) => s.toggle)

  const toggleChat = useUiStore((s) => s.toggleChat)

  const projectPath = useStore((s) => s.projectPath)

  const hasClaudeTab = tabs.some((tab) => tab.kind === 'claude')
  const hasCodexTab = tabs.some((tab) => tab.kind === 'codex')

  const t = useTheme()
  // Accumulates partial terminal data until a newline arrives
  const terminalBuffer = useRef('')
  // Auto-done timer: if no PTY output for 4s, mark command as finished
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Only capture PTY output while a /pathly command is actively running
  useEffect(() => {
    const matchingTab = tabs.find((tab) => tab.kind === targetKind)
    if (!matchingTab) return

    const tabId = matchingTab.id
    const unsub = window.pathly?.terminal?.onData(tabId, (data) => {
      if (!useChatStore.getState().isCommandRunning) return

      // Reset the idle timer on every chunk of data
      if (idleTimer.current) clearTimeout(idleTimer.current)
      idleTimer.current = setTimeout(() => {
        // No output for 4 seconds → assume command finished
        useChatStore.getState().setCommandRunning(false)
      }, 4000)

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
      if (idleTimer.current) clearTimeout(idleTimer.current)
      unsub?.()
    }
  }, [targetKind, tabs, appendOutputLine])

  // Pre-embed all skill descriptions once on first mount
  useEffect(() => {
    preEmbedSkills(loadSkills())
      .then(() => setEmbedReady(true))
      .catch(() => setEmbedReady(false))
  }, [setEmbedReady])

  async function handleSend(): Promise<void> {
    const text = inputValue.trim()
    if (!text) return

    // Stop any previous command capture when starting a new message
    setCommandRunning(false)
    clearOutputLines()
    setInputValue('')

    // /pathly commands are routed silently — don't add them as chat messages
    if (text.startsWith('/pathly')) {
      const parts = text.trim().split(/\s+/)
      const skill = parts[1] || ''
      const command = parts.slice(1).join(' ')
      setCurrentMatch({ skill, confidence: 1.0, command: command ? `/pathly ${command}` : text, description: '' })
      return
    }

    const userMsg = {
      id: crypto.randomUUID(),
      role: 'user' as const,
      content: text,
      status: 'done' as const,
    }
    addMessage(userMsg)

    // Run embed routing and POST /chat in parallel
    setIsEmbedding(true)
    const [matches, context] = await Promise.all([
      matchIntent(text),
      buildPathlyContext(),
    ])
    setIsEmbedding(false)

    const topMatch = matches[0] ?? null
    const rest = matches.slice(1)

    if (topMatch && topMatch.confidence >= 0.4) {
      setCurrentMatch(topMatch)
      setAltMatches(rest)
    } else {
      setCurrentMatch(null)
      setAltMatches([])
    }

    const assistantMsg = {
      id: crypto.randomUUID(),
      role: 'assistant' as const,
      content: '',
      status: 'streaming' as const,
    }
    addMessage(assistantMsg)
    setLoading(true)

    let streamedContent = ''
    try {
      const res = await fetch(`${PATHLY_API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          context,
          history: messages.map((m) => ({ role: m.role, content: m.content })),
          ...(topMatch && topMatch.confidence >= 0.4
            ? { matchedSkill: topMatch.skill, skillDescription: topMatch.description }
            : {}),
        }),
      })

      const reader = res.body?.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      if (!topMatch || topMatch.confidence < 0.4) {
        streamedContent = 'No matching skill found. '
        updateLastMessage({ content: streamedContent })
      }

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
              streamedContent += payload.text
              updateLastMessage({ content: streamedContent })
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

    if (autoApprove && topMatch && topMatch.confidence >= 0.65) {
      await handleRun()
    }
  }

  function handleSkillClick(command: string): void {
    setInputValue(command)
  }

  async function handleRun(): Promise<void> {
    if (!currentMatch) return
    const cmd = currentMatch.command
    setCurrentMatch(null)   // dismiss card immediately
    setAltMatches([])
    clearOutputLines()
    setCommandRunning(true)
    await writeToTerminal(targetKind, cmd, projectPath, tabs, addTab, open, toggle)
  }

  function handleReject(): void {
    setCurrentMatch(null)
    setCommandRunning(false)
    clearOutputLines()
  }

  function handleSelectAlt(skill: string): void {
    setCurrentMatch({ skill, confidence: 1.0, command: `/pathly ${skill}`, description: '' })
    setCommandRunning(false)
    clearOutputLines()
  }

  const outputStatus = isLoading ? 'running' : 'done'

  return (
    <div
      ref={chatRef}
      className={styles.panel}
      style={{ background: t.bgBase, borderLeft: t.border, fontFamily: t.fontFamilyBase, width }}
    >
      {/* Left-edge drag handle — drag to resize */}
      <div className={styles.resizeHandle} onMouseDown={onDragStart} />
      <ConductorHeader hasClaudeTab={hasClaudeTab} hasCodexTab={hasCodexTab} onToggleChat={toggleChat} onClearChat={clearMessages} />
      <SkillsPanel onSkillClick={handleSkillClick} />
      <MessageList />
      {currentMatch !== null && (
        <MatchCard
          match={currentMatch}
          alts={altMatches}
          onRun={() => { void handleRun() }}
          onReject={handleReject}
          onSelectAlt={handleSelectAlt}
        />
      )}
      {/* Show snippet while running OR after done (until next message clears it) */}
      {outputLines.length > 0 && (
        <OutputSnippet
          target={targetKind === 'claude' ? 'claude-code' : 'codex'}
          status={isCommandRunning ? 'running' : 'done'}
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
