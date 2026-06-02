import { useHQ } from './useHQ'
import { ChatHeader } from './ChatHeader/ChatHeader'
import { SkillsPanel } from './SkillsPanel/SkillsPanel'
import { MessageList } from './MessageList/MessageList'
import { ChatInput } from './ChatInput/ChatInput'
import { MatchCard } from './MatchCard/MatchCard'
import { PathlyMenuCard } from './PathlyMenuCard/PathlyMenuCard'
import { AutomationCard } from './AutomationCard/AutomationCard'
import { StepQueue } from './StepQueue/StepQueue'
import { FlowControlBar } from './FlowControlBar/FlowControlBar'
import { StageStatusStrip } from './StageStatusStrip/StageStatusStrip'
import { RunnerLogCard } from './RunnerLogCard/RunnerLogCard'
import { useRunnerStore } from '../../store/runnerStore'
import { useBrightskyStore } from '../../store/brightskyStore'
import styles from './index.module.css'

export function HQ(): JSX.Element {
  const chat = useHQ()
  const thinkingLabel = useBrightskyStore((s) => s.thinkingLabel)
  const toolCallInProgress = useBrightskyStore((s) => s.toolCallInProgress)
  const runHistory = useRunnerStore((s) => s.runHistory)

  return (
    <div
      ref={chat.chatRef}
      className={styles.panel}
    >
      {/* Left-edge drag handle — drag to resize */}
      <div className={styles.resizeHandle} onMouseDown={chat.onDragStart} />
      <ChatHeader hasClaudeTab={chat.hasClaudeTab} hasCodexTab={chat.hasCodexTab} hasShellTab={chat.hasShellTab} hasAntigravityTab={chat.hasAntigravityTab} targetKind={chat.targetKind} onSetTarget={chat.setTargetKind} onToggleChat={chat.toggleChat} onClearChat={chat.handleClearAll} sessions={chat.brightskyAuthenticated ? [] : undefined} onSelectSession={(id) => useBrightskyStore.getState().setSessionId(id)} />
      <FlowControlBar />
      <StageStatusStrip />
      <RunnerLogCard docked />
      {runHistory.map((run, i) => (
        <RunnerLogCard key={`hist-${i}`} historicalRun={run} onDismiss={() => useRunnerStore.getState().removeHistoricalRun(i)} />
      ))}
      <SkillsPanel onSkillClick={chat.handleSkillClick} />
      {/* Pipeline menu — permanent, FSM-state-driven */}
      {chat.menuVisible ? <PathlyMenuCard menu={chat.activeMenu!} onSelect={chat.handleMenuSelect} isOpen={chat.menuCardOpen} onToggle={() => chat.setMenuCardOpen((v) => !v)} /> : null}
      {/* Pushed menu — transient, skill-triggered with TTL progress bar */}
      {chat.pushedMenu ? (
        <PathlyMenuCard
          menu={chat.pushedMenu}
          onSelect={(item) => { chat.handleMenuSelect(item); chat.setPushedMenu(null) }}
          onDismiss={() => chat.setPushedMenu(null)}
          onExpire={() => chat.setPushedMenu(null)}
          isOpen={chat.pushedMenuOpen}
          onToggle={() => chat.setPushedMenuOpen((v) => !v)}
        />
      ) : null}
      {thinkingLabel && (
        <div className={styles.thinkingBar}>
          <span className={styles.thinkingDot} />
          {thinkingLabel}
        </div>
      )}
      {toolCallInProgress && (
        <div className={styles.toolBar}>
          <span className={styles.toolDot} />
          Using tool: {toolCallInProgress}...
        </div>
      )}
      <MessageList />
      {chat.automationMessages.length > 0 && chat.automationMessages[chat.automationMessages.length - 1].automationPlan && (
        <>
          <AutomationCard
            intent={chat.automationMessages[chat.automationMessages.length - 1].automationPlan!.intent}
            stepCount={chat.automationMessages[chat.automationMessages.length - 1].automationPlan!.steps.length}
            schemaAvailable={(chat.automationMessages[chat.automationMessages.length - 1].automationPlan!.steps.length > 0)}
            onRunAll={() => void chat.handleRunAll(chat.automationMessages[chat.automationMessages.length - 1].automationPlan!.steps)}
            onStepByStep={chat.handleStepByStep}
          />
          {chat.automationStatus !== 'idle' && <StepQueue />}
        </>
      )}
      {chat.currentMatch !== null && (
        <MatchCard
          match={chat.currentMatch}
          alts={chat.altMatches}
          onRun={() => { void chat.handleRun() }}
          onReject={chat.handleReject}
          onSelectAlt={chat.handleSelectAlt}
        />
      )}
      {/* Show a snippet per target — both can be visible simultaneously */}
      {chat.renderTerminalCard('claude', chat.claudeTabId, chat.claudeOutput)}
      {chat.renderTerminalCard('codex', chat.codexTabId, chat.codexOutput)}
      {chat.renderTerminalCard('shell', chat.shellTabId, chat.shellOutput)}
      {chat.renderTerminalCard('antigravity', chat.antigravityTabId, chat.outputByTarget.antigravity)}
      <ChatInput
        value={chat.inputValue}
        onChange={chat.setInputValue}
        onSend={chat.handleSend}
        onStop={chat.handleStop}
        isLoading={chat.isLoading}
        disabled={chat.isLoading}
        onToggleMiniTerminal={() => {
          if (chat.hasActiveTerminal) chat.setHiddenMiniCards((s) => ({ ...s, [chat.targetKind]: !s[chat.targetKind] }))
        }}
        onLaunchMiniTerminal={(kind) => { void chat.launchMiniTerminal(kind) }}
        miniTerminalActive={chat.miniTerminalVisible}
        miniTerminalKind={chat.hasActiveTerminal ? chat.targetKind : undefined}
      />
    </div>
  )
}
