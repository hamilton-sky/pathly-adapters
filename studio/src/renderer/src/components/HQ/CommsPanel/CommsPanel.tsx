import React, { useState } from 'react'
import { Check } from 'lucide-react'
import type { BoardScope, MessageType } from '../../CommandCenter/types'
import { CommsMsgList } from './CommsMsgList'
import { CommsInput } from './CommsInput'
import { SearchBar } from './SearchBar/SearchBar'
import { SingleAgentButton } from './SingleAgentButton/SingleAgentButton'
import { BoardViewToggle, type BoardView } from './BoardViewToggle/BoardViewToggle'
import { GoalsView } from './GoalsView/GoalsView'
import { NewGoalButton } from './GoalsView/NewGoalButton'
import { EvaluateBoardButton } from './GoalsView/EvaluateBoardButton'
import { ArtifactsView } from './ArtifactsView/ArtifactsView'
import { useCommsPanel } from './hooks/useCommsPanel'
import { useStore } from '../../../store'
import { apiStartFlow } from '../../../store/commsApi'
import s from './CommsPanel.module.css'

// Which chips each panel type shows, and their default on/off state.
// Feature panel reads come from feature.scope (backend-synced).
// Project/global panels use independent local state — toggling one
// never affects the other.
const PANEL_SCOPES: Record<BoardScope, BoardScope[]> = {
  feature: ['feature', 'project', 'global'],
  project: ['project', 'global'],
  global:  ['global'],
}
const LOCAL_DEFAULTS: Record<BoardScope, Record<BoardScope, boolean>> = {
  feature: { feature: true, project: true, global: true },
  project: { feature: false, project: true, global: true },
  global:  { feature: false, project: false, global: true },
}

export function CommsPanel({ scope, mainFeature }: { scope: BoardScope; mainFeature: string }) {
  const {
    messages, feature, flashId, post, answer, resolve, toggleScope, del, editMessage,
    supersede, attach, runSingleAgent, searchResults, searchTerm, runSearch, clearSearch,
  } = useCommsPanel(scope, mainFeature)
  const [type, setType] = useState<MessageType>(scope === 'feature' ? 'nudge' : 'decision')
  const [composeText, setComposeText] = useState('')
  const [boardView, setBoardView] = useState<BoardView>('messages')
  const projectPath = useStore((st) => st.projectPath)

  const boardKey = scope === 'feature' ? mainFeature : scope

  // Send to agent: the message comes from the modal (NOT the board input box).
  // Post it to the board as a nudge so there's a record, then run the configured
  // agent on it — passing the text as instructions so the agent gets it directly.
  const handleRunAgent = (cfg: {
    agent?: string; skill?: string; systemPrompt?: string; interactive?: boolean; adapter?: string; progress?: string; message?: string
  }): void => {
    const { message, ...config } = cfg
    const t = (message ?? '').trim()
    if (t) post('nudge', t)
    runSingleAgent({ ...config, instructions: t || undefined })
  }

  // Run a board-scoped flow (not tied to a goal/DAG) on this board's topic. The
  // runner spawns each stage as a terminal — same path as the Start button.
  const handleRunFlow = (flow: string, opts: { interactive: boolean }): void => {
    const projectRoot = projectPath.replace(/\\/g, '/').replace(/\/$/, '')
    void apiStartFlow(boardKey, flow, { projectRoot, interactive: opts.interactive })
  }
  // Independent per-panel reads — only used for project/global panels.
  // Feature panel reads are authoritative from feature.scope.
  const [localReads, setLocalReads] = useState<Record<BoardScope, boolean>>(LOCAL_DEFAULTS[scope])

  const panelScopes = PANEL_SCOPES[scope]

  const getActive = (k: BoardScope) =>
    scope === 'feature' ? (feature?.scope[k] ?? false) : localReads[k]

  const handleToggle = (k: BoardScope) => {
    if (scope === 'feature') {
      toggleScope(k)
    } else {
      setLocalReads((r) => ({ ...r, [k]: !r[k] }))
    }
  }

  return (
    <>
      <SearchBar value={searchTerm} onSearch={runSearch} onClear={clearSearch} />
      <BoardViewToggle
        view={boardView}
        onChange={setBoardView}
        rightAction={boardView === 'goals'
          ? <><EvaluateBoardButton boardKey={boardKey} /><NewGoalButton onCreate={(text) => post('goal', text)} /></>
          : undefined}
      />

      {boardView === 'messages' && (
        <CommsMsgList
          scope={scope}
          messages={messages}
          searchResults={searchResults}
          searchTerm={searchTerm}
          flashId={flashId}
          onAnswer={answer}
          onResolve={resolve}
          onDelete={del}
          onSupersede={supersede}
        />
      )}
      {boardView === 'goals' && (
        <GoalsView
          messages={messages}
          onEditGoal={(goalId, text) => editMessage(goalId, text)}
        />
      )}
      {boardView === 'artifacts' && (
        <ArtifactsView messages={messages} onDelete={del} onSupersede={supersede} />
      )}

      <div className={s.foot}>
        <div className={s.scopeRow}>
          <span className={s.lbl}>Reads:</span>
          {panelScopes.map((k) => {
            const active = getActive(k)
            return (
              <button
                key={k}
                type="button"
                className={s.scopeChk}
                {...(active ? { 'data-on': '' } : {})}
                {...(active ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
                onClick={() => handleToggle(k)}
              >
                <span className={s.box}>{active && <Check size={8} />}</span>
                {k.charAt(0).toUpperCase() + k.slice(1)}
              </button>
            )
          })}
          <SingleAgentButton boardKey={boardKey} onRun={handleRunAgent} onRunFlow={handleRunFlow} />
        </div>
        <CommsInput
          scope={scope}
          mainFeature={mainFeature}
          type={type}
          onTypeChange={setType}
          value={composeText}
          onChange={setComposeText}
          onSend={(text) => { post(type, text); setComposeText('') }}
          onAttachPath={(path, atype) => {
            const mine = [...messages].reverse().find((m) => m.from === 'you')
            if (mine) attach(mine.id, path, atype)
          }}
        />
      </div>
    </>
  )
}
