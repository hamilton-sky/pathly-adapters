// The comms store's public shape: every piece of state and every action the renderer can call.
//
// Split out so the store file is implementation, not declaration — and so a component that only
// needs the type does not pull in the store's whole dependency graph.

import type { Boards, Feature, Message, BoardScope, MessageType, FeatureStatus, Stage } from '../../components/CommandCenter/types'
import type { RunGoalOpts, DecomposeMode } from '../commsApi'

// One global-search result: a message plus the board it lives on, so the UI can
// jump to that board and flash the matched message.
export interface GlobalSearchHit {
  boardKey: string
  boardScope: BoardScope
  boardLabel: string
  /** Position in the board's relevance-ranked results (0 = best RRF/semantic hit). */
  rank: number
  message: Message
}

// ── Store shape ──────────────────────────────────────────────────────

export interface CommsState {
  features: Feature[]
  boards: Boards

  pendingCount: (featureId: string) => number
  messagesFor: (scope: BoardScope, mainFeature: string) => Message[]
  appendMessage: (key: string, message: Message) => void

  loadBoard: (scope: BoardScope, key: string, projectRoot: string) => Promise<void>
  loadFeatures: (projectPath: string) => Promise<void>

  post: (key: string, type: MessageType, text: string, stage?: Stage | null) => string
  answer: (featureId: string, messageId: string, optionId: string) => void
  resolve: (key: string, messageId: string, mode: 'block' | 'note' | 'ignore') => Promise<void>
  setFeatureStatus: (featureId: string, status: FeatureStatus, stage?: Stage) => void
  toggleScope: (featureId: string, scope: BoardScope, projectRoot: string) => void
  /** Remove any board message (force soft-delete; recoverable from trash). */
  deleteMessage: (key: string, messageId: string) => void
  /** Edit a message's text in place (e.g. rename a goal). */
  editMessage: (key: string, messageId: string, text: string) => void
  /** Edit a task's text by id — resolves the board key internally (like runTask), so a
   *  caller without a board key (e.g. TaskCard) can edit in place. */
  editTaskText: (taskId: string, text: string) => void

  // Per-board one-shot flash: highlight + scroll to a single message on a board,
  // keyed by board key (feature id / 'project' / 'global'). Set on a fresh post and
  // on a global-search result jump; auto-clears. Drives the .flash animation.
  flashId: Record<string, string | null>
  flashMessage: (boardKey: string, messageId: string) => void

  // Global search — fan-out across every board (all features + project + global),
  // each hit tagged with its origin board so a click can navigate there and flash it.
  globalQuery: string
  globalHits: GlobalSearchHit[] | null
  globalSearching: boolean
  runGlobalSearch: (query: string) => Promise<void>
  clearGlobalSearch: () => void

  supersede: (key: string, oldId: string, newId: string) => void
  attach: (key: string, messageId: string, path: string, atype?: Message['atype']) => void

  // C2 — single-agent run state keyed by board (e.g. feature id, 'project', 'global')
  boardRunState: Record<string, 'idle' | 'running' | 'busy' | 'done'>
  /** Epoch ms when the board run started — drives the elapsed clock in RunPill. */
  boardRunStart: Record<string, number>
  runSingleAgent: (key: string, opts: { agent?: string; skill?: string; systemPrompt?: string; interactive?: boolean; adapter?: string; instructions?: string; progress?: string; abilityIds?: string[]; promptOverride?: string }) => void
  /** Run the evaluator on a board: classify its content and propose concrete tasks.
   *  `systemPrompt` carries the optional evaluation lens; `instructions` carries
   *  the optional extra-instructions box. */
  runEvaluator: (key: string, opts?: { adapter?: string; systemPrompt?: string; instructions?: string; progress?: string; promptOverride?: string; abilityIds?: string[] }) => void
  /** Decompose a whole FEATURE board into sibling goals (light/full/consultation rigor).
   *  `stageOverrides` — the flow gate's transient {state: prompt} trims (FlowGatePreview),
   *  applied only when rigor='consultation'. */
  decomposeFeature: (key: string, rigor: 'light' | 'full' | 'consultation', opts?: { adapter?: string; stageOverrides?: Record<string, string> }) => void
  /** Decompose the whole PROJECT board into sibling features (light/full/consultation rigor).
   *  `stageOverrides` — the flow gate's transient {state: prompt} trims (FlowGatePreview),
   *  applied only when rigor='consultation'. */
  decomposeProject: (key: string, rigor: 'light' | 'full' | 'consultation', opts?: { adapter?: string; stageOverrides?: Record<string, string> }) => void
  /** Run a board-scoped FSM flow (debug/explore/test/team/…) with the board-run pill + timer.
   *  `stageOverrides` — the flow gate's transient {state: prompt} trims (FlowGatePreview). */
  startBoardFlow: (key: string, flow: string, opts?: { interactive?: boolean; stageOverrides?: Record<string, string> }) => void
  /** Update a board's run state from a board_run SSE phase (running/done/stopped). */
  markBoardRunPhase: (key: string, phase: string) => void
  stopBoard: (key: string) => void

  // Goal DAG run state keyed by goal message id
  goalRunState: Record<string, 'idle' | 'running' | 'busy' | 'done'>
  /** Epoch ms when the goal run started — drives the elapsed clock in RunPill. */
  goalRunStart: Record<string, number>
  runGoal: (goal_id: string, executor?: string, opts?: RunGoalOpts) => void
  /** Run ONE task headlessly (claim → build → complete); its task_status drives the UI. */
  runTask: (taskId: string, opts?: { adapter?: string; abilityIds?: string[]; promptOverride?: string }) => void
  /** Stop a running single-task run (reverts it to pending). */
  stopTask: (taskId: string) => void
  /** Epoch ms when a per-task run started — drives the task pill's elapsed timer. */
  taskRunStart: Record<string, number>
  /** Decompose a goal into a task DAG (planner = fast, consultation = deep). `stageOverrides` —
   *  the flow gate's transient {state: prompt} trims (FlowGatePreview), applied only when
   *  mode='consultation'. */
  decomposeGoal: (goal_id: string, mode: DecomposeMode, opts?: { adapter?: string; model?: string; progress?: string; abilityIds?: string[]; promptOverride?: string; stageOverrides?: Record<string, string> }) => void
  /** Update a goal's run state from a goal_run/goal_decompose SSE phase. */
  markGoalRunPhase: (goal_id: string, phase: string) => void
  stopGoal: (goal_id: string) => void

  // Per-artifact offline-summarizer status, keyed by the artifact's MESSAGE id.
  summaryStatus: Record<string, 'summarizing' | 'ready' | 'failed'>
  /** Update from a summarizing / summary_ready / summary_failed SSE event. */
  markSummaryStatus: (
    messageId: string,
    status: 'summarizing' | 'ready' | 'failed',
    error?: string,
  ) => void

  /** On mount, rehydrate the board/goal/flow run pills for a project from the PERSISTED run
   *  registry: re-verify each entry against the authoritative backend (board-lock holder /
   *  FSM runner status) and either repopulate the pill (running + original start + watcher) or
   *  clear the stale entry — so a run still alive after a full reload reappears, and one that
   *  finished while the app was closed does not falsely show. */
  rehydrateActiveRuns: (projectRoot: string) => Promise<void>
}
