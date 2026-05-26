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
  const outputByTarget = useChatStore((s) => s.outputByTarget)
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
  const setCommandRunning = useChatStore((s) => s.setCommandRunning)

  const claudeOutput = outputByTarget.claude
  const codexOutput = outputByTarget.codex

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
  // Per-target buffers and idle timers
  const terminalBuffers = useRef<Record<string, string>>({ claude: '', codex: '' })
  const idleTimers = useRef<Record<string, ReturnType<typeof setTimeout> | null>>({ claude: null, codex: null })

  // Subscribe to BOTH claude and codex tabs simultaneously — each tracks independently
  useEffect(() => {
    const kinds = ['claude', 'codex'] as const
    const unsubs: Array<(() => void) | undefined> = []

    for (const kind of kinds) {
      const matchingTab = tabs.find((tab) => tab.kind === kind)
      if (!matchingTab) continue

      const tabId = matchingTab.id
      const unsub = window.pathly?.terminal?.onData(tabId, (data) => {
        if (!useChatStore.getState().outputByTarget[kind].running) return

        // Reset this target's idle timer
        if (idleTimers.current[kind]) clearTimeout(idleTimers.current[kind]!)
        idleTimers.current[kind] = setTimeout(() => {
          useChatStore.getState().setCommandRunning(kind, false)
        }, 12000)

        terminalBuffers.current[kind] = (terminalBuffers.current[kind] ?? '') + stripAnsi(data)
        const parts = terminalBuffers.current[kind].split('\n')
        terminalBuffers.current[kind] = parts.pop() ?? ''
        for (const line of parts) {
          const trimmed = line.replace(/\r/g, '').trim()
          if (trimmed.length > 0) appendOutputLine(kind, trimmed)
        }
      })
      unsubs.push(unsub)
    }

    return () => {
      terminalBuffers.current = { claude: '', codex: '' }
      for (const kind of kinds) {
        if (idleTimers.current[kind]) clearTimeout(idleTimers.current[kind]!)
      }
      unsubs.forEach((u) => u?.())
    }
  }, [tabs, appendOutputLine])

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
    setCommandRunning(targetKind, false)
    clearOutputLines(targetKind)
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

    // Run embed routing and context fetch in parallel.
    // Always clear isEmbedding even if matchIntent throws (model download fail etc.)
    setIsEmbedding(true)
    let matches: Awaited<ReturnType<typeof matchIntent>> = []
    let context: Awaited<ReturnType<typeof buildPathlyContext>>
    try {
      ;[matches, context] = await Promise.all([
        matchIntent(text),
        buildPathlyContext(),
      ])
    } catch {
      // Embedding failed (e.g. model download error) — continue with no match
      context = { fsmStage: 'unknown', featureName: '', skills: [], studioSchema: [] }
    } finally {
      setIsEmbedding(false)
    }

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

    // Try the Python server for an LLM explanation first.
    // If the server is down or has no /chat route, fall back to a local
    // response built from match data — never show "Chat server unavailable."
    let usedServer = false
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

      if (res.ok) {
        usedServer = true
        const reader = res.body?.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let streamedContent = ''

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
      }
    } catch { /* server unreachable — fall through to local response */ }

    // Fallback: server was down, returned non-ok, or has no /chat route.
    // Build a useful response locally from match data — no error shown.
    if (!usedServer) {
      if (topMatch && topMatch.confidence >= 0.4) {
        const pct = Math.round(topMatch.confidence * 100)
        const stage = context.fsmStage !== 'unknown' && context.fsmStage
          ? `\n\nCurrent pipeline stage: **${context.fsmStage}**${context.featureName ? ` (${context.featureName})` : ''}.`
          : ''
        updateLastMessage({
          content: `Matched **${topMatch.command}** (${pct}% confidence)\n\n${topMatch.description}${stage}\n\nClick **Run** to send it to the terminal.`,
          status: 'done',
        })
      } else {
        updateLastMessage({
          content: `No skill matched your message (best score < 40%).\n\nTry rephrasing, or pick a skill from the panel above.\n\nAvailable: ${context.skills.join(', ')}.`,
          status: 'done',
        })
      }
    }

    setLoading(false)

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
    clearOutputLines(targetKind)
    setCommandRunning(targetKind, true)
    await writeToTerminal(targetKind, cmd, projectPath, tabs, addTab, open, toggle)
  }

  function handleReject(): void {
    setCurrentMatch(null)
    setCommandRunning(targetKind, false)
    clearOutputLines(targetKind)
  }

  function handleSelectAlt(skill: string): void {
    setCurrentMatch({ skill, confidence: 1.0, command: `/pathly ${skill}`, description: '' })
    setCommandRunning(targetKind, false)
    clearOutputLines(targetKind)
  }

  /** Trash button — wipes everything visible in the panel */
  function handleClearAll(): void {
    clearMessages()
    clearOutputLines()       // no arg = clears both targets
    setCurrentMatch(null)
    setAltMatches([])
    setCommandRunning('claude', false)
    setCommandRunning('codex', false)
    setLoading(false)
  }

  return (
    <div
      ref={chatRef}
      className={styles.panel}
      style={{ background: t.bgBase, borderLeft: t.border, fontFamily: t.fontFamilyBase, width }}
    >
      {/* Left-edge drag handle — drag to resize */}
      <div className={styles.resizeHandle} onMouseDown={onDragStart} />
      <ConductorHeader hasClaudeTab={hasClaudeTab} hasCodexTab={hasCodexTab} onToggleChat={toggleChat} onClearChat={handleClearAll} />
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
      {/* Show a snippet per target — both can be visible simultaneously */}
      {claudeOutput.lines.length > 0 && (
        <OutputSnippet
          target="claude-code"
          status={claudeOutput.running ? 'running' : 'done'}
          lines={claudeOutput.lines}
        />
      )}
      {codexOutput.lines.length > 0 && (
        <OutputSnippet
          target="codex"
          status={codexOutput.running ? 'running' : 'done'}
          lines={codexOutput.lines}
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
