import { useState, useEffect, useRef } from 'react'
import { useChatStore } from '../../store/chatStore'
import { useAutomationStore } from '../../store/automationStore'
import { useTerminalStore } from '../../store/terminalStore'
import { useStore } from '../../store'
import { useUiStore } from '../../store/uiStore'
import { useTheme } from '../../useTheme'
import { writeToTerminal } from '../../lib/launchTerminal'
import { buildPathlyContext } from '../../lib/pathlyContext'
import { matchIntent, preEmbedSkills } from '../../lib/embedRouter'
import { askLlm, getEngine, askOllama } from '../../lib/llmBridge'
import { useModelStore } from '../../store/modelStore'
import { WEB_LLM_MODELS } from '../../data/models'
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
    // NOTE: \r is intentionally NOT stripped here — handled in feedBuffer below
}

/** Returns true for noisy progress/spinner lines that should not appear in the snippet */
function isNoisyLine(line: string): boolean {
  if (line.length <= 2) return true
  if (/^Working\s*\(/.test(line)) return true
  if (/^[-─-╿\s]+$/.test(line)) return true
  return false
}

/**
 * Feed a raw PTY chunk into a per-target line buffer with correct \r semantics.
 * \r alone = "go to start of current line" (overwrite), not a line terminator.
 * This prevents partial-word artifacts from spinner/progress lines.
 */
function feedBuffer(buf: string, data: string): { buf: string; lines: string[] } {
  const stripped = stripAnsi(data)
  // Normalise Windows \r\n → \n first, then handle lone \r as overwrite
  const normalized = stripped.replace(/\r\n/g, '\n')
  const segments = normalized.split('\r')

  let current = buf
  for (let i = 0; i < segments.length; i++) {
    if (i > 0) {
      // Lone \r: discard current partial line back to last \n
      const lastNl = current.lastIndexOf('\n')
      current = lastNl >= 0 ? current.slice(0, lastNl + 1) : ''
    }
    current += segments[i]
  }

  const parts = current.split('\n')
  const remaining = parts.pop() ?? ''
  const lines: string[] = []
  for (const line of parts) {
    const trimmed = line.trim()
    if (trimmed.length > 0 && !isNoisyLine(trimmed)) lines.push(trimmed)
  }
  return { buf: remaining, lines }
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
  const [llmAvailable, setLlmAvailable] = useState<boolean | null>(null)

  const ollamaAvailable = useModelStore((s) => s.ollamaAvailable)
  const ollamaModelIds = useModelStore((s) => s.ollamaModelIds)
  const setOllama = useModelStore((s) => s.setOllama)
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
  const setTargetKind = useChatStore((s) => s.setTargetKind)
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
  const shellOutput = outputByTarget.shell

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
  const terminalBuffers = useRef<Record<string, string>>({ claude: '', codex: '', shell: '' })
  const idleTimers = useRef<Record<string, ReturnType<typeof setTimeout> | null>>({ claude: null, codex: null, shell: null })

  // Subscribe to claude, codex AND shell tabs simultaneously
  useEffect(() => {
    const kinds = ['claude', 'codex', 'shell'] as const
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

        const result = feedBuffer(terminalBuffers.current[kind] ?? '', data)
        terminalBuffers.current[kind] = result.buf
        for (const line of result.lines) {
          appendOutputLine(kind, line)
        }
      })
      unsubs.push(unsub)
    }

    return () => {
      terminalBuffers.current = { claude: '', codex: '', shell: '' }
      for (const kind of kinds) {
        if (idleTimers.current[kind]) clearTimeout(idleTimers.current[kind]!)
      }
      unsubs.forEach((u) => u?.())
    }
  }, [tabs, appendOutputLine])

  // Check LLM backend availability once on mount.
  // node-llama-cpp may hang on Electron <33 — treat any non-resolution as false after 4s.
  useEffect(() => {
    const timeout = setTimeout(() => setLlmAvailable(false), 4000)
    window.pathly.llm.isAvailable()
      .then((ok) => { clearTimeout(timeout); setLlmAvailable(ok) })
      .catch(() => { clearTimeout(timeout); setLlmAvailable(false) })
    return () => clearTimeout(timeout)
  }, [])

  // Check if Ollama is running and which models are installed
  useEffect(() => {
    window.pathly.llm.ollamaAvailable()
      .then(({ available, models }) => setOllama(available, models))
      .catch(() => setOllama(false, []))
  }, [setOllama])

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
      context = { fsmStage: 'unknown', featureName: '', skills: ['plan','po','storm','build','review','test','retro','explore','debug','design','fix','status','log','end'], studioSchema: [] }
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

    // ── Strong skill match: respond instantly from skill data, no LLM needed ──
    // Phi-4-mini (and small local models) have no knowledge of Pathly skills
    // and will hallucinate descriptions. When confidence ≥ 0.45 we already
    // know exactly what the skill does — just show it.
    if (topMatch && topMatch.confidence >= 0.45) {
      const pct = Math.round(topMatch.confidence * 100)
      const stage = context.fsmStage !== 'unknown' && context.fsmStage
        ? `\n\nCurrent pipeline stage: **${context.fsmStage}**${context.featureName ? ` (${context.featureName})` : ''}.`
        : ''
      addMessage({
        id: crypto.randomUUID(),
        role: 'assistant' as const,
        content: `Matched **${topMatch.command}** (${pct}% confidence)\n\n${topMatch.description}${stage}\n\nClick **Run** to execute, or ask me anything.`,
        status: 'done' as const,
      })
      if (autoApprove && topMatch.confidence >= 0.65) {
        await handleRun()
      }
      return
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

    {
      // ── Determine which LLM backend to use ───────────────────────────────
      const skillList = context.skills.filter(Boolean).join(', ') || 'plan, po, build, review, test, retro'
      const systemPrompt = buildSystemPrompt(context, topMatch)

      const showSkillFallback = (note?: string): void => {
        if (topMatch && topMatch.confidence >= 0.4) {
          const pct = Math.round(topMatch.confidence * 100)
          const stage = context.fsmStage !== 'unknown' && context.fsmStage
            ? `\n\nCurrent pipeline stage: **${context.fsmStage}**${context.featureName ? ` (${context.featureName})` : ''}.`
            : ''
          updateLastMessage({
            content: `Matched **${topMatch.command}** (${pct}% confidence)\n\n${topMatch.description}${stage}\n\nClick **Run** to send it to the terminal.${note ?? ''}`,
            status: 'done',
          })
        } else {
          updateLastMessage({
            content: `No skill matched your message.\n\nTry rephrasing, or pick a skill from the panel above.\n\nAvailable: ${skillList}.${note ?? ''}`,
            status: 'done',
          })
        }
      }

      const selectedModelId = useModelStore.getState().selectedModelId
      const selectedModel = WEB_LLM_MODELS.find((m) => m.id === selectedModelId)
      const selectedModelName = selectedModel?.name ?? selectedModelId

      // Check if Ollama has this model installed (match by exact tag or base name)
      const ollamaTag = selectedModel?.ollamaId ?? ''
      const ollamaBase = ollamaTag.split(':')[0]
      const currentOllamaModels = useModelStore.getState().ollamaModelIds
      const ollamaHasModel = currentOllamaModels.some(
        (m) => m === ollamaTag || m.startsWith(ollamaBase + ':') || m.startsWith(ollamaBase + '-')
      )

      const localModelCached = useModelStore.getState().cachedModelIds.includes(selectedModelId)
      const localAvailable = llmAvailable === true && localModelCached

      if (ollamaHasModel) {
        // ── Ollama path — stream from local Ollama server ─────────────────
        try {
          let fullText = ''
          await askOllama(text, systemPrompt, ollamaTag, (chunk) => {
            fullText += chunk
            updateLastMessage({ content: fullText, status: 'streaming' })
          })
          updateLastMessage({
            content: fullText.trim() || '_(empty response — try a different model)_',
            status: 'done',
          })
        } catch (err) {
          console.error('[Ollama] chat error:', err)
          showSkillFallback('\n\n_(Ollama error — is Ollama still running?)_')
        } finally {
          setLoading(false)
        }
      } else if (localAvailable) {
        // ── node-llama-cpp path — Electron 33+ only ───────────────────────
        try {
          await getEngine(selectedModelId)
          let fullText = ''
          await askLlm(text, systemPrompt, (chunk) => {
            fullText += chunk
            updateLastMessage({ content: fullText, status: 'streaming' })
          })
          updateLastMessage({
            content: fullText.trim() || '⚠ The model returned an empty response. Try re-downloading or switching to Phi-4 Mini.',
            status: 'done',
          })
        } catch (err) {
          console.error('[LLM] chat error:', err)
          showSkillFallback('\n\n_(Local AI unavailable — upgrade Electron to 33+ for local inference.)_')
        } finally {
          setLoading(false)
        }
      } else {
        // ── No LLM available — always respond immediately ─────────────────
        const isOllamaRunning = useModelStore.getState().ollamaAvailable
        if (!isOllamaRunning) {
          // Ollama not running: explain how to get LLM responses
          const hint = '\n\n---\n_No AI backend available. To enable responses:_\n' +
            '_1. Install [Ollama](https://ollama.ai) and run `ollama pull ' + (ollamaTag || 'phi4-mini') + '`_\n' +
            '_2. Start Ollama, then reload the app._'
          showSkillFallback(hint)
        } else if (!ollamaHasModel && ollamaTag) {
          // Ollama is running but model not pulled yet
          updateLastMessage({
            content: `📥 **${selectedModelName}** isn't installed in Ollama yet.\n\nOpen the model selector (top-right) and click **↓ Pull via Ollama** to install it.\n\nOr run: \`ollama pull ${ollamaTag}\``,
            status: 'done',
          })
        } else {
          showSkillFallback()
        }
        setLoading(false)
      }
    }

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
    setCommandRunning('shell', false)
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
      <ConductorHeader hasClaudeTab={hasClaudeTab} hasCodexTab={hasCodexTab} targetKind={targetKind} onSetTarget={setTargetKind} onToggleChat={toggleChat} onClearChat={handleClearAll} />
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
      {shellOutput.lines.length > 0 && (
        <OutputSnippet
          target="shell"
          status={shellOutput.running ? 'running' : 'done'}
          lines={shellOutput.lines}
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
