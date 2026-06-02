import React, { useState, useEffect, useRef } from 'react'
import { useRunnerStore } from '../../store/runnerStore'
import type { DecisionMenuItem, RunnerStatus, SessionKind, AgentQuestionOption } from '../../store/runnerStore'
import { useBrightskyStore } from '../../store/brightskyStore'
import { brightskyClient } from '../../lib/brightskyClient'
import { useChatStore } from '../../store/chatStore'
import { useAutomationStore } from '../../store/automationStore'
import { useTerminalStore } from '../../store/terminalStore'
import type { TerminalTab } from '../../types/terminal'
import { useStore } from '../../store'
import { useUiStore } from '../../store/uiStore'
import { writeToTerminal } from '../../lib/launchTerminal'
import { buildPathlyContext, invalidatePathlyContext, subscribeToMenuUpdates, type PushedMenu } from '../../lib/pathlyContext'
import { useToastStore } from '../../store/toastStore'
import { hasEmbeddedSkills, matchIntent, matchIntentByName, preEmbedSkills } from '../../lib/embedRouter'
import { askLlm, getEngine, askOllama, abortLlm } from '../../lib/llmBridge'
import { splitThinkingContent } from '../../lib/thinkingParser'
import { useModelStore } from '../../store/modelStore'
import { WEB_LLM_MODELS } from '../../data/models'
import { loadSkills } from '../../lib/skillsManifest'
import { MiniTerminalCard } from './MiniTerminalCard/MiniTerminalCard'
import { useChatResize } from './useChatResize'
import * as xtermRegistry from '../Terminal/xtermRegistry'
import { feedBuffer, buildSystemPrompt } from './chatUtils'
import type { PathlyMenuItem } from '../../lib/pathlyContext'

export function useHQ() {
  const [inputValue, setInputValue] = useState('')
  const [llmAvailable, setLlmAvailable] = useState<boolean | null>(null)
  const [pathlyContext, setPathlyContext] = useState<Awaited<ReturnType<typeof buildPathlyContext>> | null>(null)
  const [hiddenMiniCards, setHiddenMiniCards] = useState<Record<'claude' | 'codex' | 'shell' | 'antigravity', boolean>>({
    claude: false,
    codex: false,
    shell: false,
    antigravity: false,
  })
  const [menuCardOpen, setMenuCardOpen] = useState(true)
  const [pushedMenu, setPushedMenu] = useState<PushedMenu | null>(null)
  const [pushedMenuOpen, setPushedMenuOpen] = useState(true)

  const brightskyAuthenticated = useBrightskyStore((s) => s.authenticated)

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
  const chatMode = useChatStore((s) => s.chatMode)
  const setChatMode = useChatStore((s) => s.setChatMode)

  const automationStatus = useAutomationStore((s) => s.status)
  const automationMessages = messages.filter((m) => m.mode === 'automation')

  const claudeOutput = outputByTarget.claude
  const codexOutput = outputByTarget.codex
  const shellOutput = outputByTarget.shell

  const tabs = useTerminalStore((s) => s.tabs)
  const addTabSilent = useTerminalStore((s) => s.addTabSilent)
  const open = useTerminalStore((s) => s.open)
  const toggle = useTerminalStore((s) => s.toggle)
  const openTab = useTerminalStore((s) => s.openTab)
  const tabIdByKind = useTerminalStore((s) => s.tabIdByKind)
  const rememberTabForKind = useTerminalStore((s) => s.rememberTabForKind)
  const appendScrollback = useTerminalStore((s) => s.appendScrollback)
  const claudeTabId = tabIdByKind.claude ?? tabs.find((tab) => tab.kind === 'claude')?.id ?? null
  const codexTabId = tabIdByKind.codex ?? tabs.find((tab) => tab.kind === 'codex')?.id ?? null
  const shellTabId = tabIdByKind.shell ?? tabs.find((tab) => tab.kind === 'shell')?.id ?? null
  const antigravityTabId = tabIdByKind.antigravity ?? tabs.find((tab) => tab.kind === 'antigravity')?.id ?? null

  const TARGET_COLORS: Record<'claude' | 'codex' | 'shell' | 'antigravity', string> = {
    claude: '#38BDF8', codex: '#F59E0B', shell: '#86EFAC', antigravity: '#4285F4',
  }
  const currentTabId = targetKind === 'claude' ? claudeTabId : targetKind === 'codex' ? codexTabId : targetKind === 'antigravity' ? antigravityTabId : shellTabId
  const currentOutput = targetKind === 'claude' ? claudeOutput : targetKind === 'codex' ? codexOutput : targetKind === 'antigravity' ? outputByTarget.antigravity : shellOutput
  const hasActiveTerminal = !!currentTabId
  const miniTerminalVisible = hasActiveTerminal && !hiddenMiniCards[targetKind]

  const toggleChat = useUiStore((s) => s.toggleChat)

  const projectPath = useStore((s) => s.projectPath)
  const activeTopic = useStore((s) => s.activeTopic)

  const hasClaudeTab = tabs.some((tab) => tab.kind === 'claude')
  const hasCodexTab = tabs.some((tab) => tab.kind === 'codex')
  const hasShellTab = tabs.some((tab) => tab.kind === 'shell')
  const hasAntigravityTab = tabs.some((tab) => tab.kind === 'antigravity')
  const activeMenu = pathlyContext?.menu ?? null
  const menuKey = activeMenu ? `${activeMenu.state}:${activeMenu.feature}` : null
  const [menuDismissedKey, setMenuDismissedKey] = useState<string | null>(null)
  const menuVisible = activeMenu !== null && menuKey !== menuDismissedKey

  const terminalBuffers = useRef<Record<string, string>>({ claude: '', codex: '', shell: '', antigravity: '' })
  const idleTimers = useRef<Record<string, ReturnType<typeof setTimeout> | null>>({ claude: null, codex: null, shell: null, antigravity: null })
  const streamTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const streamPending = useRef<ReturnType<typeof splitThinkingContent> | null>(null)

  function queueAssistantStream(fullText: string): void {
    streamPending.current = splitThinkingContent(fullText)
    if (streamTimer.current) return
    streamTimer.current = setTimeout(() => {
      const pending = streamPending.current
      streamTimer.current = null
      streamPending.current = null
      if (pending) updateLastMessage({ content: pending.content, thinking: pending.thinking, status: 'streaming' })
    }, 60)
  }

  function finishAssistantStream(fullText: string, fallback: string): void {
    if (streamTimer.current) {
      clearTimeout(streamTimer.current)
      streamTimer.current = null
    }
    streamPending.current = null
    const { thinking, content } = splitThinkingContent(fullText)
    updateLastMessage({ content: content || fallback, thinking, status: 'done' })
  }

  useEffect(() => {
    const kinds = ['claude', 'codex', 'shell', 'antigravity'] as const
    const unsubs: Array<(() => void) | undefined> = []

    for (const kind of kinds) {
      const tabId = tabIdByKind[kind] ?? tabs.find((tab) => tab.kind === kind)?.id
      if (!tabId) continue

      const unsub = window.pathly?.terminal?.onData(tabId, (data) => {
        appendScrollback(tabId, data)
        if (!useChatStore.getState().outputByTarget[kind].running) return

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
      terminalBuffers.current = { claude: '', codex: '', shell: '', antigravity: '' }
      for (const kind of kinds) {
        if (idleTimers.current[kind]) clearTimeout(idleTimers.current[kind]!)
      }
      unsubs.forEach((u) => u?.())
    }
  }, [tabs, tabIdByKind, appendOutputLine, appendScrollback])

  useEffect(() => {
    const timeout = setTimeout(() => setLlmAvailable(false), 4000)
    window.pathly.llm.isAvailable()
      .then((ok) => { clearTimeout(timeout); setLlmAvailable(ok) })
      .catch(() => { clearTimeout(timeout); setLlmAvailable(false) })
    return () => clearTimeout(timeout)
  }, [])

  useEffect(() => {
    window.pathly.llm.ollamaAvailable()
      .then(({ available, models }) => setOllama(available, models))
      .catch(() => setOllama(false, []))
  }, [setOllama])

  useEffect(() => {
    let cancelled = false

    const fetchContext = (): void => {
      buildPathlyContext(projectPath ?? undefined, activeTopic ?? undefined)
        .then((ctx) => { if (!cancelled) setPathlyContext(ctx) })
        .catch(() => { if (!cancelled) setPathlyContext(null) })
    }

    invalidatePathlyContext(projectPath ?? undefined)
    fetchContext()

    const interval = window.setInterval(fetchContext, 5000)

    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [projectPath, activeTopic])

  useEffect(() => {
    const unsubscribe = subscribeToMenuUpdates(
      projectPath ?? '',
      (menu) => setPathlyContext((prev) => prev ? { ...prev, menu } : null),
      (pushed) => { setPushedMenu(pushed); setPushedMenuOpen(true) },
      () => setPushedMenu(null),
    )
    return unsubscribe
  }, [projectPath])

  useEffect(() => {
    if (!activeTopic) return   // topic required by server — skip until one is active
    const { setRunnerState, setDecisionMenu } = useRunnerStore.getState()
    const lastCostRef = { current: 0 }
    const retryCountRef = { current: 0 }
    let es: EventSource | null = null          // hoisted — accessible in cleanup
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null

    function connect(): void {
      try {
        const url = `http://127.0.0.1:8765/events/runner?topic=${encodeURIComponent(activeTopic ?? '')}`
        es = new EventSource(url)
        es.onopen = () => { retryCountRef.current = 0; setRunnerState({ errorMessage: null }) }  // reset backoff + clear error banner on reconnect
        es.onmessage = (e: MessageEvent) => {
          try {
            const data = JSON.parse(e.data as string) as { type: string; [key: string]: unknown }
            if (data.type === 'STAGE_CHANGE') {
              setRunnerState({
                stage: data.stage as string,
                adapter: data.adapter as string | null,
                status: data.status as RunnerStatus,
              })
              const log = useRunnerStore.getState().stageLog
              const last = log[log.length - 1]
              const isReconnect = last && last.endedAt === null && last.stage === (data.stage as string)
              if (!isReconnect) {
                useRunnerStore.getState().recordStageStart(data.stage as string, data.adapter as string | null, null)
              }
            } else if (data.type === 'DECISION_MENU') {
              setRunnerState({ status: 'blocked' })
              setDecisionMenu(data.items as DecisionMenuItem[])
              useRunnerStore.getState().setLogCardExpanded(true)
              useToastStore.getState().push('Runner is waiting for your decision', 'info')
            } else if (data.type === 'AGENT_QUESTION') {
              setRunnerState({ status: 'blocked' })
              useRunnerStore.getState().setAgentQuestion({
                question: data.question as string,
                options: data.options as AgentQuestionOption[],
              })
              useToastStore.getState().push('Agent is waiting for your answer', 'info')
            } else if (data.type === 'RUNNER_STATUS') {
              setRunnerState({ status: data.status as RunnerStatus })
              if (data.status === 'running') {
                useRunnerStore.getState().setAgentQuestion(null)
              }
            } else if (data.type === 'COST_UPDATE') {
              const now = Date.now()
              if (now - lastCostRef.current >= 200) {
                lastCostRef.current = now
                setRunnerState({ cost: data.cost_usd as number })
              }
            } else if (data.type === 'SESSION') {
              setRunnerState({ sessionKind: data.kind as SessionKind })
            } else if (data.type === 'RUNNER_WARNING') {
              useToastStore.getState().push(`Runner warning: ${(data.reason as string) ?? 'unknown'}`, 'info')
            } else if (data.type === 'RUNNER_ERROR') {
              setRunnerState({ errorMessage: data.message as string, status: 'error' })
            } else if (data.type === 'TERMINAL_SPAWN') {
              const tab_id = data.tab_id as string
              const run_id = data.run_id as string
              const adapter = data.adapter as string
              const label = (data.label as string | undefined) ?? adapter
              const cwd = (data.cwd as string | undefined) ?? useRunnerStore.getState().projectRoot ?? ''
              const prompt = (data.prompt as string | undefined) ?? ''
              const stage = (data.stage as string | undefined) ?? ''
              useTerminalStore.getState().addTab(tab_id, label, 'left', adapter as TerminalTab['kind'])
              useTerminalStore.getState().openTab(tab_id)
              useTerminalStore.setState((s) => ({
                tabs: s.tabs.map((t) => t.id === tab_id ? { ...t, runnerOwned: true } : t),
              }))
              useRunnerStore.getState().attachTerminalToStage(tab_id, 'terminal')
              if (prompt) useRunnerStore.getState().recordStagePrompt(prompt)
              const argv = Array.isArray(data.argv) ? (data.argv as string[]) : undefined
              void window.pathly.terminal.registerRunner(tab_id, activeTopic ?? '', run_id, label)
                .then(() => window.pathly.terminal.spawn(tab_id, cwd, undefined, argv))
                .then(() => {
                  fetch('http://127.0.0.1:8765/runner/terminal/started', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tab_id, run_id, topic: activeTopic, pid: 0 }),
                  }).catch(() => { /* non-blocking */ })
                })
                .catch(() => { /* spawn failure — PTY unavailable */ })
            } else if (data.type === 'TERMINAL_SIGNAL') {
              const signal = data.signal as string
              if (signal === 'term') {
                const tabId = (data.tab_id as string | undefined) ?? useRunnerStore.getState().activeRunnerTabId
                if (tabId) void window.pathly.terminal.kill(tabId).catch(() => { /* PTY may already be gone */ })
              }
            } else if (data.type === 'RUN_STARTED') {
              useRunnerStore.getState().snapshotRun()
              useRunnerStore.getState().setRunnerState({ errorMessage: null, cost: 0, stage: null, adapter: null, sessionKind: null })
            } else if (data.type === 'RUN_COMPLETE') {
              // Snapshot the finished/aborted run → moves stageLog to history
              // → docked banner clears (stageLog becomes empty → card returns null)
              // → historical card appears (collapsed) in its place
              useRunnerStore.getState().snapshotRun()
              useRunnerStore.getState().setRunnerState({ status: (data.status as RunnerStatus) ?? 'idle' })
            }
          } catch { /* ignore parse errors */ }
        }
        es.onerror = () => {
          es?.close()
          es = null
          // Exponential backoff: 3s → 6s → 12s → … capped at 30s
          const delay = Math.min(3000 * Math.pow(2, retryCountRef.current), 30000)
          retryCountRef.current += 1
          setRunnerState({ errorMessage: 'Server offline — reconnecting…' })
          reconnectTimeout = setTimeout(connect, delay)
        }
      } catch { /* EventSource not available — silently skip */ }
    }

    connect()

    return () => {
      if (reconnectTimeout !== null) clearTimeout(reconnectTimeout)
      es?.close()    // now accessible — closes the live connection on unmount
    }
  }, [activeTopic])

  useEffect(() => {
    const unsub = window.pathly.terminal.onStageResult((tabId, data) => {
      const r = data as { result?: string; total_cost_usd?: number; duration_ms?: number; usage?: { input_tokens?: number; output_tokens?: number; cache_read_input_tokens?: number; cache_creation_input_tokens?: number } }
      useRunnerStore.getState().recordStageResult(
        tabId,
        r.result ?? '',
        r.total_cost_usd ?? 0,
        r.usage?.input_tokens ?? 0,
        r.usage?.output_tokens ?? 0,
        r.usage?.cache_read_input_tokens ?? 0,
        r.usage?.cache_creation_input_tokens ?? 0,
        r.duration_ms ?? 0,
      )
    })
    return unsub
  }, [])

  // Sync active tab → runner: when the user switches feature tabs, bind the runner to that feature.
  useEffect(() => {
    if (activeTopic && projectPath) {
      useRunnerStore.getState().setRunnerConfig(activeTopic, projectPath)
    }
  }, [activeTopic, projectPath])

  // Fallback: if no tab is open yet, ask the server which feature was last active.
  useEffect(() => {
    if (activeTopic || !projectPath) return   // tab already set — no need to query
    const url = `http://127.0.0.1:8765/status?project_root=${encodeURIComponent(projectPath)}`
    fetch(url)
      .then((r) => r.json())
      .then((data: Record<string, unknown>) => {
        const feature = data.feature as string | undefined
        const root = (data.project_root as string | undefined) ?? projectPath
        if (feature && !useRunnerStore.getState().topic) {
          useRunnerStore.getState().setRunnerConfig(feature, root)
        }
      })
      .catch(() => { /* server may be offline */ })
  }, [activeTopic, projectPath])

  useEffect(() => {
    preEmbedSkills(loadSkills(), (pct) => setEmbedProgress(pct))
      .then(() => { setEmbedProgress(100); setEmbedReady(true) })
      .catch(() => { setEmbedProgress(0); setEmbedReady(false) })
  }, [setEmbedReady, setEmbedProgress])

  async function handleBrightskySend(content: string): Promise<void> {
    const { connected, wsUrl, accessToken, sessionId, authenticated } = useBrightskyStore.getState()
    if (!authenticated || !accessToken) {
      useBrightskyStore.getState().setAuthError('Please connect to Brightsky first.')
      return
    }
    if (!connected) {
      brightskyClient.connect(wsUrl, accessToken)
    }
    await brightskyClient.sendMessage(content, sessionId)
  }

  function handleStop(): void {
    abortLlm()
    if (streamTimer.current) {
      clearTimeout(streamTimer.current)
      streamTimer.current = null
    }
    streamPending.current = null
    updateLastMessage({ status: 'done' })
    setLoading(false)
  }

  async function handleSend(): Promise<void> {
    const text = inputValue.trim()
    if (!text) return

    setCommandRunning(targetKind, false)
    clearOutputLines(targetKind)
    setInputValue('')

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

    if (chatMode === 'claude') {
      setLoading(true)
      const assistantMsg = {
        id: crypto.randomUUID(),
        role: 'assistant' as const,
        content: '',
        status: 'streaming' as const,
        source: 'claude-code',
      }
      addMessage(assistantMsg)
      try {
        const addBackgroundTab = (id: string, label: string, _pane?: 'left' | 'right', kind?: 'shell' | 'claude' | 'codex' | 'antigravity'): void => {
          addTabSilent(id, label, kind)
          xtermRegistry.getOrCreate(id, { fontSize: 12 })
        }
        await writeToTerminal(
          'claude',
          text,
          projectPath,
          tabs,
          addBackgroundTab,
          open,
          toggle,
          rememberTabForKind,
          openTab,
        )
      } catch {
        updateLastMessage({ content: 'Claude Code terminal is not available. Please open the terminal first.', status: 'done' })
        setLoading(false)
      }
      return
    }

    if (useModelStore.getState().selectedModelId === 'brightsky') {
      await handleBrightskySend(text)
      return
    }

    setIsEmbedding(true)
    let matches: Awaited<ReturnType<typeof matchIntent>> = []
    let context: Awaited<ReturnType<typeof buildPathlyContext>>
    const canUseEmbedding = useChatStore.getState().embedReady && hasEmbeddedSkills()
    try {
      ;[matches, context] = await Promise.all([
        canUseEmbedding ? matchIntent(text) : Promise.resolve(matchIntentByName(text, loadSkills())),
        buildPathlyContext(projectPath ?? undefined),
      ])
    } catch {
      context = { fsmStage: 'unknown', featureName: '', skills: ['plan','po','storm','build','review','test','retro','explore','debug','design','fix','status','log','end'], studioSchema: [], menu: null, pushedMenu: null }
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

    {
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
      const responseMode = useModelStore.getState().responseMode
      const selectedModel = WEB_LLM_MODELS.find((m) => m.id === selectedModelId)
      const selectedModelName = selectedModel?.name ?? selectedModelId

      const ollamaTag = selectedModel?.ollamaId ?? ''
      const ollamaBase = ollamaTag.split(':')[0]
      const currentOllamaModels = useModelStore.getState().ollamaModelIds
      const ollamaHasModel = currentOllamaModels.some(
        (m) => m === ollamaTag || m.startsWith(ollamaBase + ':') || m.startsWith(ollamaBase + '-')
      )

      const localModelCached = useModelStore.getState().cachedModelIds.includes(selectedModelId)
      const localAvailable = llmAvailable === true && localModelCached

      const llmPrompt = topMatch && topMatch.confidence >= 0.4
        ? `Skill: ${topMatch.command}\nDescription: ${topMatch.description}\n\nBased only on the description above, explain this skill in one sentence, then say "Click **Run** to execute."`
        : text

      if (ollamaHasModel) {
        try {
          let fullText = ''
          await askOllama(llmPrompt, systemPrompt, ollamaTag, (chunk) => {
            fullText += chunk
            queueAssistantStream(fullText)
          }, responseMode === 'deep' && selectedModel?.thinking === true)
          finishAssistantStream(fullText, '_(empty response - try a different model)_')
        } catch (err) {
          console.error('[Ollama] chat error:', err)
          showSkillFallback('\n\n_(Ollama error — is Ollama still running?)_')
        } finally {
          setLoading(false)
        }
      } else if (localAvailable) {
        try {
          await getEngine(selectedModelId)
          let fullText = ''
          await askLlm(llmPrompt, systemPrompt, (chunk) => {
            fullText += chunk
            queueAssistantStream(fullText)
          })
          finishAssistantStream(fullText, 'The model returned an empty response. Try re-downloading or switching to Phi-4 Mini.')
        } catch (err) {
          console.error('[LLM] chat error:', err)
          showSkillFallback('\n\n_(Local AI unavailable — upgrade Electron to 33+ for local inference.)_')
        } finally {
          setLoading(false)
        }
      } else {
        const isOllamaRunning = useModelStore.getState().ollamaAvailable
        if (!isOllamaRunning) {
          const hint = '\n\n---\n_No AI backend available. To enable responses:_\n' +
            '_1. Install [Ollama](https://ollama.ai) and run `ollama pull ' + (ollamaTag || 'phi4-mini') + '`_\n' +
            '_2. Start Ollama, then reload the app._'
          showSkillFallback(hint)
        } else if (!ollamaHasModel && ollamaTag) {
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
    if (!projectPath) {
      console.error('[handleRun] no project path set — open a project before running a skill')
      return
    }
    const cmd = currentMatch.command
    setCurrentMatch(null)
    setAltMatches([])
    clearOutputLines(targetKind)
    setCommandRunning(targetKind, true)
    setHiddenMiniCards((state) => ({ ...state, [targetKind]: false }))
    try {
      const addBackgroundTab = (id: string, label: string, _pane?: 'left' | 'right', kind?: 'shell' | 'claude' | 'codex' | 'antigravity'): void => {
        addTabSilent(id, label, kind)
        xtermRegistry.getOrCreate(id, { fontSize: 12 })
      }
      await writeToTerminal(
        targetKind,
        cmd,
        projectPath,
        tabs,
        addBackgroundTab,
        open,
        toggle,
        rememberTabForKind,
        openTab,
        { revealFullTerminal: false }
      )
    } catch (err) {
      console.error('[handleRun] terminal write failed:', err)
      setCommandRunning(targetKind, false)
    }
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

  async function launchMiniTerminal(kind: 'shell' | 'claude' | 'codex' | 'antigravity'): Promise<void> {
    if (!projectPath) return
    const existing = tabs.find((tab) => tab.kind === kind)
    if (existing) {
      setHiddenMiniCards((s) => ({ ...s, [kind]: false }))
      return
    }
    const id = crypto.randomUUID()
    const label = kind === 'claude' ? 'Claude Code' : kind === 'codex' ? 'Codex' : kind === 'antigravity' ? 'Antigravity' : 'Shell'
    addTabSilent(id, label, kind)
    xtermRegistry.getOrCreate(id, { fontSize: 12 })
    await window.pathly?.terminal?.spawn(id, projectPath, kind === 'shell' ? undefined : kind === 'antigravity' ? 'agy' : kind)
    setHiddenMiniCards((s) => ({ ...s, [kind]: false }))
  }

  function handleClearAll(): void {
    clearMessages()
    clearOutputLines()
    setCurrentMatch(null)
    setAltMatches([])
    setCommandRunning('claude', false)
    setCommandRunning('codex', false)
    setCommandRunning('shell', false)
    setCommandRunning('antigravity', false)
    setLoading(false)
  }

  function renderTerminalCard(
    kind: 'claude' | 'codex' | 'shell' | 'antigravity',
    tabId: string | null,
    output: typeof claudeOutput
  ): JSX.Element | null {
    if (tabId) {
      if (hiddenMiniCards[kind]) return null
      return (
        <MiniTerminalCard
          key={`${kind}-${tabId}`}
          tabId={tabId}
          target={kind}
          status={output.running ? 'running' : 'done'}
          previewLines={output.lines}
          onOpenFullTerminal={() => {
            openTab(tabId)
            document.dispatchEvent(new CustomEvent('pathly:focus-terminal-tab', { detail: { tabId } }))
          }}
          onClose={() => setHiddenMiniCards((state) => ({ ...state, [kind]: true }))}
          onKill={() => {
            void (async () => {
              try { await window.pathly?.terminal?.kill(tabId) } catch { /* PTY may already be gone */ }
              xtermRegistry.dispose(tabId)
              useTerminalStore.getState().closeTab(tabId)
              setCommandRunning(kind, false)
              clearOutputLines(kind)
              setHiddenMiniCards((state) => ({ ...state, [kind]: true }))
            })()
          }}
        />
      )
    }

    return null
  }

  function handleAgentAnswer(answer: string): void {
    if (!activeTopic) return
    useRunnerStore.getState().setAgentQuestion(null)
    fetch('http://127.0.0.1:8765/runner/agent-answer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: activeTopic, answer }),
    }).catch(() => { /* non-blocking */ })
  }

  function handleMenuSelect(item: PathlyMenuItem): void {
    if (!projectPath) return
    setMenuDismissedKey(menuKey)
    const kind = item.terminal_kind ?? 'claude'
    setCommandRunning(kind, true)
    setHiddenMiniCards((s) => ({ ...s, [kind]: false }))
    const addBackgroundTab = (id: string, label: string, _pane?: 'left' | 'right', tabKind?: 'shell' | 'claude' | 'codex' | 'antigravity'): void => {
      addTabSilent(id, label, tabKind)
      xtermRegistry.getOrCreate(id, { fontSize: 12 })
    }
    void writeToTerminal(
      kind,
      item.command,
      projectPath,
      tabs,
      addBackgroundTab,
      open,
      toggle,
      rememberTabForKind,
      openTab,
      { revealFullTerminal: false }
    ).catch((err) => {
      console.error('[handleMenuSelect] terminal write failed:', err)
      setCommandRunning(kind, false)
    })
  }

  return {
    inputValue,
    setInputValue,
    llmAvailable,
    pathlyContext,
    hiddenMiniCards,
    setHiddenMiniCards,
    menuCardOpen,
    setMenuCardOpen,
    pushedMenu,
    setPushedMenu,
    pushedMenuOpen,
    setPushedMenuOpen,
    brightskyAuthenticated,
    ollamaAvailable,
    ollamaModelIds,
    chatRef,
    onDragStart,
    width,
    messages,
    currentMatch,
    altMatches,
    outputByTarget,
    targetKind,
    autoApprove,
    isLoading,
    claudeOutput,
    codexOutput,
    shellOutput,
    tabs,
    claudeTabId,
    codexTabId,
    shellTabId,
    antigravityTabId,
    TARGET_COLORS,
    currentTabId,
    currentOutput,
    hasActiveTerminal,
    miniTerminalVisible,
    toggleChat,
    projectPath,
    activeTopic,
    hasClaudeTab,
    hasCodexTab,
    hasShellTab,
    hasAntigravityTab,
    activeMenu,
    menuVisible,
    menuDismissedKey,
    automationStatus,
    automationMessages,
    setTargetKind,
    handleBrightskySend,
    handleStop,
    handleSend,
    handleRunAll,
    handleStepByStep,
    handleSkillClick,
    handleRun,
    handleReject,
    handleSelectAlt,
    launchMiniTerminal,
    handleClearAll,
    renderTerminalCard,
    handleMenuSelect,
    handleAgentAnswer,
    queueAssistantStream,
    finishAssistantStream,
    chatMode,
    setChatMode,
  }
}
