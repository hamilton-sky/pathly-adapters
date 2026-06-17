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
import { apiStartFlow, apiPostArtifact, resolveFeaturePath, scopeToParams } from '../../../store/commsApi'
import { useToastStore } from '../../../store/toastStore'
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

// Guess an artifact's display type from its extension (for the card icon/preview).
function inferAtype(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  if (ext === 'md') return 'md'
  if (ext === 'pdf') return 'pdf'
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) return 'image'
  if (ext === 'json') return 'json'
  return 'code'
}

// Avoid overwriting an existing artifact of the same name: report.pdf → report (1).pdf.
function dedupeName(name: string, taken: Set<string>): string {
  if (!taken.has(name)) return name
  const dot = name.lastIndexOf('.')
  const stem = dot > 0 ? name.slice(0, dot) : name
  const ext = dot > 0 ? name.slice(dot) : ''
  let n = 1
  while (taken.has(`${stem} (${n})${ext}`)) n += 1
  return `${stem} (${n})${ext}`
}

// One toast summarizing a drop: success for what was added, error for what failed.
function notifyDrop(posted: number, failed: number, failHint?: string): void {
  const push = useToastStore.getState().push
  if (posted) push(`Added ${posted} artifact${posted === 1 ? '' : 's'} to the board`, 'success')
  if (failed) push(`${failed} file${failed === 1 ? '' : 's'} couldn't be added${failHint ? ` — ${failHint}` : ''}`, 'error')
}

export function CommsPanel({ scope, mainFeature }: { scope: BoardScope; mainFeature: string }) {
  const {
    messages, feature, flashId, post, answer, resolve, toggleScope, del, editMessage,
    supersede, attach, runSingleAgent, searchResults, searchTerm, runSearch, clearSearch, reload,
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

  // Drop files onto the Artifacts view → copy each into the feature's artifacts/
  // dir (binary-safe, in-place reference would break if the original moves) → post
  // it as an artifact card. The dropped files then become board content the
  // evaluator can read. Feature boards copy into the feature; project/global into a
  // shared uploads dir.
  const handleDropFiles = async (files: File[]): Promise<void> => {
    const projectRoot = projectPath.replace(/\\/g, '/').replace(/\/$/, '')
    if (!projectRoot || !files.length) return
    const params = scopeToParams(scope, boardKey)
    const base = scope === 'feature'
      ? await resolveFeaturePath(projectRoot, boardKey)
      : `${projectRoot}/pathly/.uploads/${boardKey}`
    const dir = `${base}/artifacts`
    // Dedupe against files already in the dest dir + names taken earlier this drop.
    const taken = new Set<string>(await window.pathly.fs.list(dir).catch(() => []))
    let posted = 0
    let failed = 0
    for (const file of files) {
      const src = window.pathly.fs.pathForFile(file)
      if (!src) { failed += 1; continue }
      const name = dedupeName(file.name, taken)
      taken.add(name)
      try {
        await window.pathly.fs.copy(src, `${dir}/${name}`)
        const id = await apiPostArtifact(boardKey, params.board, params.scope, `Uploaded ${name}`, `${dir}/${name}`, inferAtype(name))
        if (id) posted += 1
        else failed += 1
      } catch { failed += 1 }
    }
    notifyDrop(posted, failed, 'files must be under your home folder')
    if (posted) reload()
  }

  // Files dragged from the workspace tree are already in the project — reference
  // their existing path as an artifact (no copy needed).
  const handleDropPaths = async (items: { path: string; name: string }[]): Promise<void> => {
    if (!items.length) return
    const params = scopeToParams(scope, boardKey)
    let posted = 0
    let failed = 0
    for (const it of items) {
      const path = it.path.replace(/\\/g, '/')
      const id = await apiPostArtifact(boardKey, params.board, params.scope, `Added ${it.name}`, path, inferAtype(it.name))
      if (id) posted += 1
      else failed += 1
    }
    notifyDrop(posted, failed)
    if (posted) reload()
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
        <ArtifactsView messages={messages} onDelete={del} onSupersede={supersede} onDropFiles={handleDropFiles} onDropPaths={handleDropPaths} />
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
