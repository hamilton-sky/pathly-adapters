import { useState, useEffect, useRef } from 'react'
import { useChatStore } from '../../store/chatStore'
import { useAutomationStore } from '../../store/automationStore'
import { useTerminalStore } from '../../store/terminalStore'
import { useStore } from '../../store'
import { useUiStore } from '../../store/uiStore'
import { useTheme } from '../../useTheme'
import { writeToTerminal } from '../../lib/launchTerminal'
import { buildPathlyContext } from '../../lib/pathlyContext'
import { PATHLY_API_BASE } from '../../lib/config'
import { matchIntent, preEmbedSkills } from '../../lib/embedRouter'
import { askWebLLM, getEngine, getCachedWebLLMModelIds } from '../../lib/webLLMEngine'
import { useModelStore } from '../../store/modelStore'
import { loadSkills } from '../../lib/skillsManifest'
import { ConductorHeader } from './ConductorHeader'
import { SkillsPanel } from './SkillsPanel'
import { MessageList } from './MessageList'
import { ChatInput } from './ChatInput'
import { MatchCard } from './MatchCard'
import { OutputSnippet } from './OutputSnippet'
import { AutomationCard } from './AutomationCard'
import { StepQueue } from './StepQueue'
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

function buildSystemPrompt(
  context: Awaited<ReturnType<typeof buildPathlyContext>>,
  topMatch: { skill: string; confidence: number; command: string; description: string } | null
): string {
  const skillList = context.skills.join(', ')
  const stageInfo = context.fsmStage !== 'unknown' && context.fsmStage
    ? `Current pipeline stage: ${context.fsmStage}${context.featureName ? ` (feature: ${context.featureName})` : ''}.`
    : 'No active pipeline stage.'
  const matchInfo = topMatch && topMatch.confidence >= 0.4
    ? `Best skill match: ${topMatch.command} (${Math.round(topMatch.confidence * 100)}% confidence) — ${topMatch.description}`
    : 'No strong skill match found.'
  const schemaInfo = context.studioSchema && context.studioSchema.length > 0
    ? `\n\n## Studio UI Elements\n${context.studioSchema.slice(0, 20).map((el) => `- ${el.screen}: ${el.label} (${el.type})`).join('\n')}`
    : ''

  return `You are the Conductor — a helpful AI assistant built into Pathly Studio.
Your job is to help users run Pathly pipeline skills and navigate the Studio UI.

${stageInfo}
Available skills: ${skillList}
${matchInfo}${schemaInfo}

When a user asks about running a skill, explain what it does and confirm the match.
Be concise (2-3 sentences). Do not invent skills that are not in the available list.`
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
  const setEmbedProgress = useChatStore((s) => s.setEmbedProgress)
  const setLoading = useChatStore((s) => s.setLoading)
  const isLoading = useChatStore((s) => s.isLoading)
  const setCommandRunning = useChatStore((s) => s.setCommandRunning)

  const automationStatus = useAutomationStore((s) => s.status)
  const automationMessages = messages.filter((m) => m.mode === 'automation')

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

  // Pre-embed all skill descriptions once on first mount.
  // Progress callback updates embedProgress (0–100) so the UI can show download state.
  useEffect(() => {
    preEmbedSkills(loadSkills(), (pct) => setEmbedProgress(pct))
      .then(() => { setEmbedProgress(100); setEmbedReady(true) })
      .catch(() => { setEmbedProgress(0); setEmbedReady(false) })
  }, [setEmbedReady, setEmbedProgress])

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
      // Embedding failed (e.g. model download error) — continue with no match.
      // Always include the known skills list so the fallback response is useful.
      context = { fsmStage: 'unknown', featureName: '', skills: loadSkills().map((s) => s.name), studioSchema: [] }
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

    const isAutomationIntent = /\b(create|make|build|add|new)\b.*\b(flow|step|state|transition)\b/i.test(text)

    const assistantMsg = {
      id: crypto.randomUUID(),
      role: 'assistant' as const,
      content: '',
      status: 'streaming' as const,
    }
    addMessage(assistantMsg)
    setLoading(true)

    if (process.env.PATHLY_CHAT_BACKEND !== 'ollama') {
      // Local WebLLM path
      const systemPrompt = buildSystemPrompt(context, topMatch)
      try {
        const selectedModelId = useModelStore.getState().selectedModelId
        const isCached = useModelStore.getState().cachedModelIds.includes(selectedModelId)
        if (!isCached) {
          // Model not downloaded yet — auto-download and show progress in the chat bubble
          updateLastMessage({ content: '⬇ Downloading model — this may take a few minutes…', status: 'streaming' })
          await getEngine(selectedModelId, (pct, progressText) => {
            useModelStore.getState().setProgress(selectedModelId, pct)
            const shardMatch = progressText?.match(/\[(\d+)\/(\d+)\]/)
            const shardLabel = shardMatch ? ` · shard ${shardMatch[1]}/${shardMatch[2]}` : ''
            updateLastMessage({
              content: `⬇ Downloading model… **${pct}%**${shardLabel}`,
              status: 'streaming',
            })
          })
          const updated = await getCachedWebLLMModelIds()
          useModelStore.getState().setCached(updated)
          useModelStore.getState().setProgress(selectedModelId, 100)
          updateLastMessage({ content: '', status: 'streaming' })
        } else {
          await getEngine(selectedModelId)
        }
        let fullText = ''
        await askWebLLM(text, systemPrompt, (chunk) => {
          fullText += chunk
          updateLastMessage({ content: fullText, status: 'streaming' })
        })
        updateLastMessage({ content: fullText, status: 'done' })
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err)
        if (msg === 'WebGPU not supported') {
          updateLastMessage({
            content: '⚠️ WebGPU is required for local AI. Enable it in Electron or set PATHLY_CHAT_BACKEND=ollama.',
            status: 'done',
          })
        } else {
          // WebLLM failed — fall back to local match response
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
      }
    } else {
      // Ollama/Python backend path (PATHLY_CHAT_BACKEND=ollama)
      let usedServer = false
      try {
        const res = await fetch(`${PATHLY_API_BASE}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text,
            message: text,
            context,
            mode: isAutomationIntent ? 'automation' : 'chat',
            studioSchema: context.studioSchema,
            history: messages.map((m) => ({ role: m.role, content: m.content })),
            ...(topMatch && topMatch.confidence >= 0.4
              ? { matchedSkill: topMatch.skill, skillDescription: topMatch.description }
              : {}),
          }),
        })

        if (res.ok) {
          usedServer = true
          const json = await res.json() as { type: string; text?: string; intent?: string; steps?: import('../../types/automation').AutomationStep[] }

          if (json.type === 'automation' && json.steps) {
            useAutomationStore.getState().setSteps(json.steps)
            updateLastMessage({
              content: '',
              status: 'done',
              mode: 'automation',
              automationPlan: { intent: json.intent ?? text, steps: json.steps },
            })
          } else {
            updateLastMessage({ content: json.text ?? '', status: 'done' })
          }
        }
      } catch { /* server unreachable — fall through to local response */ }

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
    }

    setLoading(false)

    if (autoApprove && topMatch && topMatch.confidence >= 0.65) {
      await handleRun()
    }
  }

  async function handleRunAll(steps: import('../../types/automation').AutomationStep[]): Promise<void> {
    const { setStatus, advanceToNext, setMode } = useAutomationStore.getState()
    setMode('auto')
    setStatus('running')
    for (const step of steps) {
      try {
        const result = await window.pathly.automation.executeStep(step.action)
        if (result.success) {
          advanceToNext()
        } else {
          setStatus('error')
          break
        }
      } catch {
        setStatus('error')
        break
      }
      await new Promise<void>((r) => setTimeout(r, 300))
    }
    const currentStatus = useAutomationStore.getState().status
    if (currentStatus === 'running') {
      setStatus('done')
    }
  }

  function handleStepByStep(): void {
    useAutomationStore.getState().setMode('staged')
    useAutomationStore.getState().setStatus('running')
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
      {automationMessages.length > 0 && automationMessages[automationMessages.length - 1].automationPlan && (
        <>
          <AutomationCard
            intent={automationMessages[automationMessages.length - 1].automationPlan!.intent}
            stepCount={automationMessages[automationMessages.length - 1].automationPlan!.steps.length}
            schemaAvailable={(automationMessages[automationMessages.length - 1].automationPlan!.steps.length > 0)}
            onRunAll={() => void handleRunAll(automationMessages[automationMessages.length - 1].automationPlan!.steps)}
            onStepByStep={handleStepByStep}
          />
          {automationStatus !== 'idle' && <StepQueue />}
        </>
      )}
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
