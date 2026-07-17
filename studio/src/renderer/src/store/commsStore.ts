import { create } from 'zustand'
import type { Boards, Feature, Message, BoardScope, MessageType, FeatureStatus, Stage } from '../components/CommandCenter/types'
import { RESERVED_TOPICS } from './reservedTopics'
import {
  fetchBoard,
  apiPost,
  apiAnswer,
  apiAcknowledge,
  apiToggleScope,
  apiDelete,
  apiEditMessage,
  scopeToParams,
  buildFeature,
  fetchFeatureState,
  featureBlocked,
  fetchLastSummary,
  apiRunnerDecision,
  apiRunnerAwaitingDecision,
  apiRunnerStatus,
  apiSearch,
  apiSupersede,
  apiAttach,
  apiRunBoard,
  apiStopBoard,
  apiBoardRunStatus,
  apiRunGoal,
  apiRunTask,
  apiStopTask,
  apiStopGoal,
  apiDecomposeGoal,
  apiDecomposeFeature,
  apiDecomposeProject,
  type RunGoalOpts,
  type DecomposeMode,
} from './commsApi'
import { listDirs } from '../services/pathlyApi'
import { useRunnerStore } from './runnerStore'
import { useProjectStore } from './projectStore'
import { useToastStore } from './toastStore'

function isPending(m: Message): boolean {
  return (m.type === 'question' && m.status === 'pending')
    || (m.type === 'warning' && m.status === 'open')
    || m.type === 'escalation'
}

function storageKey(scope: BoardScope, key: string): string {
  return scope === 'feature' ? key : scope
}

// Map a board KEY (a feature id, or the literal 'project'/'global') to its backend
// {board, scope}. The project board's DB scope is the project ROOT — what loadBoard
// and store.post read/write with — NOT the literal 'project', which the board never
// queries and which collides across projects in the shared central DB. Feature/global
// keys map straight through. Centralized so this project-scope trap can't recur (it
// already bit posts, artifact drops, and board runs separately).
function boardParamsForKey(key: string): { board: string; scope: string } {
  const scope: BoardScope = key !== 'project' && key !== 'global' ? 'feature' : (key as BoardScope)
  if (scope === 'project') {
    const root = useProjectStore.getState().projectPath.replace(/\\/g, '/').replace(/\/$/, '')
    return scopeToParams(scope, root)
  }
  return scopeToParams(scope, key)
}

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
  runEvaluator: (key: string, opts?: { adapter?: string; systemPrompt?: string; instructions?: string; progress?: string; promptOverride?: string }) => void
  /** Decompose a whole FEATURE board into sibling goals (light/full/consultation rigor). */
  decomposeFeature: (key: string, rigor: 'light' | 'full' | 'consultation', opts?: { adapter?: string }) => void
  /** Decompose the whole PROJECT board into sibling features (light/full/consultation rigor). */
  decomposeProject: (key: string, rigor: 'light' | 'full' | 'consultation', opts?: { adapter?: string }) => void
  /** Update a board's run state from a board_run SSE phase (running/done/stopped). */
  markBoardRunPhase: (key: string, phase: string) => void
  stopBoard: (key: string) => void

  // Goal DAG run state keyed by goal message id
  goalRunState: Record<string, 'idle' | 'running' | 'busy' | 'done'>
  /** Epoch ms when the goal run started — drives the elapsed clock in RunPill. */
  goalRunStart: Record<string, number>
  runGoal: (goal_id: string, executor?: string, opts?: RunGoalOpts) => void
  /** Run ONE task headlessly (claim → build → complete); its task_status drives the UI. */
  runTask: (taskId: string, opts?: { adapter?: string }) => void
  /** Stop a running single-task run (reverts it to pending). */
  stopTask: (taskId: string) => void
  /** Epoch ms when a per-task run started — drives the task pill's elapsed timer. */
  taskRunStart: Record<string, number>
  /** Decompose a goal into a task DAG (planner = fast, consultation = deep). */
  decomposeGoal: (goal_id: string, mode: DecomposeMode, opts?: { adapter?: string; model?: string; progress?: string; abilityIds?: string[]; promptOverride?: string }) => void
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
}

// ── Board-run completion watchers ─────────────────────────────────────
// A board run (Evaluate / single-agent) is fire-and-forget server-side: the pill
// clears only when markBoardRunPhase('done') fires from the PER-BOARD comms SSE — so
// if you navigate away (the board unmounts) or the SSE stalls, the 'done' is missed
// and the pill sticks on 'running'. These watchers live in the store (which never
// unmounts), poll the authoritative board-lock status, and clear the pill when the
// run releases the lock — the store-side analogue of the editor's client pollForFile.
const _runWatchers = new Map<string, number>()

function _stopRunWatch(key: string): void {
  const id = _runWatchers.get(key)
  if (id !== undefined) {
    window.clearInterval(id)
    _runWatchers.delete(key)
  }
}

function _startRunWatch(key: string, runId?: string): void {
  _stopRunWatch(key)
  const params = boardParamsForKey(key)
  const id = window.setInterval(() => {
    void (async () => {
      const st = useCommsStore.getState().boardRunState[key]
      // Already cleared (SSE 'done' won, or Stop was pressed) → stop watching.
      if (st !== 'running' && st !== 'busy') { _stopRunWatch(key); return }
      const status = await apiBoardRunStatus(params.board, params.scope)
      if (!status) return // unreachable (e.g. older server) — keep watching, never false-complete
      // Still ours while the lock is held by our run (or by anyone, if we lack the id).
      if (status.running && (!runId || !status.holder || status.holder === runId)) return
      _stopRunWatch(key)
      // Re-check to avoid a double 'done' if the SSE completed it between poll + now.
      if (useCommsStore.getState().boardRunState[key] === 'running') {
        useCommsStore.getState().markBoardRunPhase(key, 'done')
      }
    })()
  }, 4000)
  _runWatchers.set(key, id)
}

// Completion watch for a board-launched FSM-FLOW run (project/feature consultation). Unlike a
// single-agent board run, an FSM flow holds NO board-lock — so _startRunWatch's lock poll would
// instantly false-complete it (the pill stops while the run keeps going, visible only in the CLI
// monitor). Poll the FSM RUNNER status for the run's topic (= the board scope) instead, and clear
// the pill only when the run is genuinely terminal (done / aborted / error / gone).
function _startFsmRunWatch(key: string, scope: string): void {
  _stopRunWatch(key)
  const id = window.setInterval(() => {
    void (async () => {
      const st = useCommsStore.getState().boardRunState[key]
      if (st !== 'running' && st !== 'busy') { _stopRunWatch(key); return }
      const status = await apiRunnerStatus(scope)
      if (status === null) return // network hiccup — keep watching, never false-complete
      if (['running', 'paused', 'awaiting_decision', 'finalizing'].includes(status)) return
      _stopRunWatch(key)
      if (useCommsStore.getState().boardRunState[key] === 'running') {
        useCommsStore.getState().markBoardRunPhase(key, 'done')
      }
    })()
  }, 4000)
  _runWatchers.set(key, id)
}

// ── Goal-run completion watchers ──────────────────────────────────────
// Same rationale as the board watchers, for goal decompose/run: the "Planning…" pill
// clears only when markGoalRunPhase('done') fires from the comms SSE, so a missed 'done'
// (board unmounted / SSE stalled) strands the goal card on "Planning…" forever. A goal
// decompose/run holds its parent BOARD lock (board_busy guards concurrency), so we poll
// the same board-lock status and clear the pill once the lock releases.
const _goalWatchers = new Map<string, number>()

function _stopGoalWatch(goalId: string): void {
  const id = _goalWatchers.get(goalId)
  if (id !== undefined) {
    window.clearInterval(id)
    _goalWatchers.delete(goalId)
  }
}

// The (board, scope) a goal's lock is held under. A goal's message is loaded on exactly
// one board, so we find that board key and map it the way _startRunWatch does. Returns
// null when the goal isn't in any loaded board — the caller then relies on the SSE alone
// (no regression versus before this watcher existed).
function _goalBoardParams(goalId: string): { board: string; scope: string } | null {
  const boards = useCommsStore.getState().boards
  for (const [key, msgs] of Object.entries(boards)) {
    if (msgs.some((m) => m.id === goalId)) {
      return boardParamsForKey(key)
    }
  }
  return null
}

function _startGoalWatch(goalId: string, runId?: string): void {
  _stopGoalWatch(goalId)
  const params = _goalBoardParams(goalId)
  if (!params) return
  const id = window.setInterval(() => {
    void (async () => {
      const st = useCommsStore.getState().goalRunState[goalId]
      // Already cleared (SSE phase won, or Stop was pressed) → stop watching.
      if (st !== 'running' && st !== 'busy') { _stopGoalWatch(goalId); return }
      const status = await apiBoardRunStatus(params.board, params.scope)
      if (!status) return // unreachable — keep watching, never false-complete
      // Lock still held by our run (or by anyone, if we lack the id) → the run is live.
      if (status.running && (!runId || !status.holder || status.holder === runId)) return
      _stopGoalWatch(goalId)
      // Lock released with no 'done' SSE → force-clear (re-check to avoid a double 'done').
      if (useCommsStore.getState().goalRunState[goalId] === 'running') {
        useCommsStore.getState().markGoalRunPhase(goalId, 'done')
      }
    })()
  }, 4000)
  _goalWatchers.set(goalId, id)
}

export const useCommsStore = create<CommsState>()((set, get) => ({
  features: [],
  boards: {},

  pendingCount: (fid) => (get().boards[fid] || []).filter(isPending).length,

  messagesFor: (scope, mainFeature) =>
    get().boards[storageKey(scope, mainFeature)] || [],

  appendMessage: (key, message) =>
    set((s) => ({ boards: { ...s.boards, [key]: [...(s.boards[key] || []), message] } })),

  loadBoard: async (scope, key, projectRoot) => {
    const boardId = storageKey(scope, key)
    const params = scopeToParams(scope, scope === 'project' ? projectRoot : key)
    // GET /comms requires a non-empty feature param; use key for feature boards,
    // or 'global' / projectRoot basename for wider boards.
    const featureParam = scope === 'feature' ? key : (scope === 'global' ? 'global' : key)
    const messages = await fetchBoard(featureParam, params.board, params.scope)
    // Change-guard: the fallback poll calls this every few seconds. Skip the set (and
    // the store-wide re-render it triggers) when the board is byte-identical to what's
    // already loaded, so an idle poll costs a fetch + compare and nothing else.
    const prev = get().boards[boardId]
    if (prev && prev.length === messages.length && JSON.stringify(prev) === JSON.stringify(messages)) return
    set((s) => ({ boards: { ...s.boards, [boardId]: messages } }))
  },

  loadFeatures: async (projectPath: string) => {
    try {
      // New-style features live directly under pathly/<id>/. Exclude the structural
      // container dirs (RESERVED_TOPICS mirrors _RESERVED_TOPICS in storage_paths.py) so we
      // never surface "plans"/"features"/"goals"/… as a bogus feature card.
      const pathlyDir = `${projectPath}/pathly`
      const topLevelNames = await listDirs(pathlyDir).catch(() => [] as string[])
      const newStyleIds = topLevelNames.filter((n) => !RESERVED_TOPICS.has(n))

      // Feature-centric layout (storage-restructure Phase 1+): features live under
      // pathly/features/<id>/. This is what makes Phase-1 features show in the sidebar.
      const featureNames = await listDirs(`${pathlyDir}/features`).catch(() => [] as string[])
      // Exclude structural/reserved dir names (RESERVED_TOPICS already covers '.archive')
      // so a stray reserved-named dir under features/ — e.g. a 'project' left by a bad
      // board write + its BOARD.json mirror — is never surfaced as a feature (its section
      // id would collide with the literal project/global board section → duplicate React key).
      const featureIds = featureNames.filter((n) => !RESERVED_TOPICS.has(n))

      // Feature-centric pathly/features/<id>/ + any new-style top-level pathly/<id>/.
      const allIds = [...new Set([...featureIds, ...newStyleIds])]

      // Enrich each feature from its STATE.json (stage + conv) and feedback/ (blocked).
      const features: Feature[] = await Promise.all(
        allIds.map(async (id) => {
          const [state, blocked, last] = await Promise.all([
            fetchFeatureState(projectPath, id),
            featureBlocked(projectPath, id),
            fetchLastSummary(projectPath, id),
          ])
          return buildFeature(id, state, blocked, last)
        }),
      )
      // Change-guard (see loadBoard): the periodic refresh calls this on an interval;
      // skip the set when the feature list is unchanged so the sidebar doesn't re-render.
      if (JSON.stringify(get().features) === JSON.stringify(features)) return
      set({ features })
    } catch {
      // leave existing features list intact on error
    }
  },

  post: (key, type, text, stage) => {
    // Optimistic local id — will be replaced when the board reloads after API call
    const tempId = `temp_${Date.now()}_${Math.random().toString(36).slice(2)}`
    const m: Message = {
      id: tempId,
      type,
      from: 'you',
      ts: new Date().toISOString(),
      text,
      stage: stage ?? null,
      pinned: type === 'decision',
      readByAgent: false,
      ...(type === 'question'
        ? { status: 'pending' as const, options: [{ id: 'a', label: 'Option A' }, { id: 'b', label: 'Option B' }] }
        : {}),
    }
    set((s) => ({ boards: { ...s.boards, [key]: [...(s.boards[key] || []), m] } }))

    // Determine board/scope from key: feature boards use the key as featureId,
    // project/global use their literal scope names.
    const isFeature = key !== 'project' && key !== 'global'
    const scope: BoardScope = isFeature ? 'feature' : key as BoardScope
    // The project board's backend scope is the (project-unique) root path — the SAME
    // value loadBoard reads with — NOT the literal 'project'. Posting under 'project'
    // lands the message in a scope the board never queries, so it vanishes on the next
    // reload; the central DB is shared across projects, so 'project' would also collide.
    const projectRoot = useProjectStore.getState().projectPath.replace(/\\/g, '/').replace(/\/$/, '')
    const params = scopeToParams(scope, scope === 'project' ? projectRoot : key)

    apiPost(key, params.board, params.scope, type, text, stage).then((id) => {
      if (id) {
        // Replace temp message with server-assigned id
        set((s) => ({
          boards: {
            ...s.boards,
            [key]: (s.boards[key] || []).map((msg) => msg.id === tempId ? { ...msg, id } : msg),
          },
        }))
      }
    }).catch(() => { /* optimistic message stays */ })

    return tempId
  },

  answer: (fid, mid, opt) => {
    // Optimistic update
    set((s) => {
      const arr = s.boards[fid] || []
      const q = arr.find((m) => m.id === mid)
      if (!q || q.status === 'answered') return s
      const next = arr.map((m) => (m.id === mid ? { ...m, status: 'answered' as const, answer: opt } : m))
      return { boards: { ...s.boards, [fid]: next } }
    })

    const chosen = (get().boards[fid] || []).find((m) => m.id === mid)
    const chosenOpt = (chosen?.options || []).find((o) => o.id === opt)
    const label = chosenOpt?.label ?? opt

    apiAnswer(mid, `Use \`${label}\`. Keep it simple.`, opt).catch(() => { /* optimistic stays */ })
  },

  resolve: async (key, mid, mode) => {
    // 1. Optimistic board annotation.
    set((s) => {
      const resolution =
        mode === 'block' ? 'blocked → builder retry'
        : mode === 'note' ? 'noted as future work'
        : 'ignored'
      const arr = (s.boards[key] || []).map((m) =>
        m.id === mid ? { ...m, status: 'resolved' as const, resolution } : m)
      return { boards: { ...s.boards, [key]: arr } }
    })

    // 2. Mark handled on the board (best-effort).
    void apiAcknowledge(mid, 'you')

    // 3. mode==='note' → record the choice as a durable decision on the board.
    if (mode === 'note') {
      const params = scopeToParams('feature', key)
      const stage = get().features.find((f) => f.id === key)?.stage ?? null
      void apiPost(key, params.board, params.scope, 'decision',
        'Noted as future work (deferred from a warning).', stage)
    }

    // 4. Drive the FSM ONLY when this feature is the active awaiting-decision run.
    const { topic } = useRunnerStore.getState()
    if (topic && topic === key) {
      const options = await apiRunnerAwaitingDecision(topic)
      if (options) {
        const wanted = mode === 'block' ? 'block' : 'continue'
        const decision = options.includes(wanted)
          ? wanted
          : (options.includes('continue') ? 'continue' : options[0])
        void apiRunnerDecision(topic, decision)
      }
    }
  },

  setFeatureStatus: (fid, status, stage) => {
    set((s) => {
      const features = s.features.map((f) =>
        f.id === fid ? { ...f, status, ...(stage ? { stage } : {}) } : f)
      if (status === 'running') {
        return {
          features,
          boards: {
            ...s.boards,
            [fid]: (s.boards[fid] || []).map((m) =>
              m.type === 'warning' && m.status === 'open'
                ? { ...m, status: 'resolved' as const, resolution: 'unblocked → builder retry' }
                : m),
          },
        }
      }
      return { features }
    })
  },

  toggleScope: (fid, scope, projectRoot) => {
    // Compute the new scope from current state ONCE, then apply it both locally
    // and to the server (reading back after set() would re-flip the value).
    const feature = get().features.find((f) => f.id === fid)
    if (!feature) return
    const newScope = { ...feature.scope, [scope]: !feature.scope[scope] }
    set((s) => ({
      features: s.features.map((f) => (f.id === fid ? { ...f, scope: newScope } : f)),
    }))
    apiToggleScope(fid, projectRoot, newScope).catch(() => { /* best-effort */ })
  },

  deleteMessage: (key, messageId) => {
    // Any board message can be removed (agent posts, status lines, read messages).
    // Removes it from store state immediately and force soft-deletes server-side
    // (recoverable from trash).
    set((s) => {
      const arr = s.boards[key] || []
      if (!arr.some((x) => x.id === messageId)) return s
      return { boards: { ...s.boards, [key]: arr.filter((x) => x.id !== messageId) } }
    })
    apiDelete(messageId, true).catch(() => { /* best-effort */ })
  },

  editMessage: (key, messageId, text) => {
    // Optimistic in-place text update; the board reload reconciles. The id is
    // preserved server-side so a goal keeps its task links.
    set((s) => {
      const arr = s.boards[key] || []
      if (!arr.some((x) => x.id === messageId)) return s
      return { boards: { ...s.boards, [key]: arr.map((x) => x.id === messageId ? { ...x, text } : x) } }
    })
    apiEditMessage(messageId, text).catch(() => { /* best-effort */ })
  },

  editTaskText: (taskId, text) => {
    // Resolve which loaded board holds the task so the optimistic patch lands on it, then
    // delegate to editMessage (id preserved server-side → dependsOn links survive the edit).
    const s = get()
    const key = Object.keys(s.boards).find((k) => (s.boards[k] || []).some((m) => m.id === taskId))
    if (key) { get().editMessage(key, taskId, text); return }
    // Not in any loaded board (shouldn't happen) — still persist; a board reload reconciles.
    apiEditMessage(taskId, text).catch(() => { /* best-effort */ })
  },

  flashId: {},

  flashMessage: (boardKey, messageId) => {
    set((s) => ({ flashId: { ...s.flashId, [boardKey]: messageId } }))
    // Keep it set long enough for a freshly-opened board to mount and catch it; the
    // CSS animation is a 900ms one-shot, so nothing lingers visually after it plays.
    window.setTimeout(() => {
      set((s) => (s.flashId[boardKey] === messageId
        ? { flashId: { ...s.flashId, [boardKey]: null } }
        : s))
    }, 1600)
  },

  globalQuery: '',
  globalHits: null,
  globalSearching: false,

  runGlobalSearch: async (query) => {
    const q = query.trim()
    if (!q) { set({ globalHits: null, globalQuery: '', globalSearching: false }); return }
    set({ globalQuery: q, globalSearching: true })

    // Fan out the per-board /comms/search across every board there is — all features
    // (get().features holds them all, not just the open ones) plus project + global.
    // Each board query is tagged with its origin so a result can navigate + flash.
    const projectRoot = useProjectStore.getState().projectPath.replace(/\\/g, '/').replace(/\/$/, '')
    interface Target { boardKey: string; scope: BoardScope; label: string; feature: string; board: string; apiScope: string }
    const targets: Target[] = get().features.map((f) => {
      const p = scopeToParams('feature', f.id)
      return { boardKey: f.id, scope: 'feature', label: f.id, feature: f.id, board: p.board, apiScope: p.scope }
    })
    if (projectRoot) {
      const p = scopeToParams('project', projectRoot)
      targets.push({ boardKey: 'project', scope: 'project', label: 'Project', feature: 'project', board: p.board, apiScope: p.scope })
    }
    const gp = scopeToParams('global', 'global')
    targets.push({ boardKey: 'global', scope: 'global', label: 'Global', feature: 'global', board: gp.board, apiScope: gp.scope })

    const batches = await Promise.all(
      targets.map((t) =>
        apiSearch(q, t.feature, t.board, t.apiScope)
          .then((rows) => rows.map((m, i): GlobalSearchHit => ({
            boardKey: t.boardKey, boardScope: t.scope, boardLabel: t.label, rank: i, message: m,
          })))
          .catch(() => [] as GlobalSearchHit[]),
      ),
    )

    // Drop a stale run: a newer query started while this fan-out was in flight.
    if (get().globalQuery !== q) return
    // Each board's rows arrive relevance-ranked (RRF/cosine). Merge boards by
    // interleaving rank — every board's best hit first, then the #2s… — with
    // newest-first as the tiebreak. Not a plain ts sort: that buried relevance
    // and displayed the same order for every query.
    const hits = batches.flat().sort(
      (a, b) => a.rank - b.rank || (b.message.ts ?? '').localeCompare(a.message.ts ?? ''),
    )
    set({ globalHits: hits.slice(0, 40), globalSearching: false })
  },

  clearGlobalSearch: () => set({ globalHits: null, globalQuery: '', globalSearching: false }),

  supersede: (key, oldId, newId) => {
    set((s) => {
      const arr = (s.boards[key] || []).map((m) =>
        m.id === oldId ? { ...m, supersededBy: newId } : m)
      return { boards: { ...s.boards, [key]: arr } }
    })
    void apiSupersede(oldId, newId)
  },

  attach: (key, messageId, path, atype) => {
    set((s) => {
      const arr = (s.boards[key] || []).map((m) =>
        m.id === messageId ? { ...m, artifact: path.split(/[/\\]/).pop(), atype } : m)
      return { boards: { ...s.boards, [key]: arr } }
    })
    void apiAttach(messageId, path, atype)
  },

  boardRunState: {},
  boardRunStart: {},

  runSingleAgent: (key, opts) => {
    const now = Date.now()
    set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'running' }, boardRunStart: { ...s.boardRunStart, [key]: now } }))

    const isFeature = key !== 'project' && key !== 'global'
    // Align Studio's runner SSE subscription with this board's topic so the agent's
    // terminal actually opens: useHQ subscribes to events/runner?topic=activeTopic,
    // and the board run broadcasts TERMINAL_SPAWN to topic=<feature>. Feature boards
    // only — global/project use a topic the feature-centric activeTopic can't match.
    if (isFeature) useProjectStore.getState().setActiveTopic(key)
    const params = boardParamsForKey(key)
    // Always send the project root — it's the PTY's working directory. Sending
    // undefined for feature boards meant the agent spawned with an empty cwd, which
    // fails the PTY silently (no 'started' callback → terminal_spawn_timeout).
    const projectRoot = useProjectStore.getState().projectPath.replace(/\\/g, '/').replace(/\/$/, '')

    apiRunBoard(params.board, params.scope, 'single-agent', { ...opts, projectRoot })
      .then((res) => {
        if (res === null) {
          set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' } }))
          return
        }
        if (!res.ok && res.error === 'board_busy') {
          set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'busy' } }))
          return
        }
        // /comms/run returns 'started' immediately (the run is async). Stay 'running'
        // so the control stays green and Stop is enabled while the agent CLI is open.
        // The pill clears when the board_run 'done' phase arrives over the comms SSE →
        // markBoardRunPhase — or, if that's missed (navigated away / SSE stalled), via
        // this store-owned completion watch, which polls the board-lock and survives unmount.
        if (res.ok) _startRunWatch(key, res.run_id)
      })
      .catch(() => {
        set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' } }))
      })
  },

  runEvaluator: (key, opts = {}) => {
    const now = Date.now()
    set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'running' }, boardRunStart: { ...s.boardRunStart, [key]: now } }))

    const isFeature = key !== 'project' && key !== 'global'
    if (isFeature) useProjectStore.getState().setActiveTopic(key)
    const params = boardParamsForKey(key)
    const projectRoot = useProjectStore.getState().projectPath.replace(/\\/g, '/').replace(/\/$/, '')

    apiRunBoard(params.board, params.scope, 'evaluator', { projectRoot, ...opts })
      .then((res) => {
        if (res === null) {
          set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' } }))
          return
        }
        if (!res.ok && res.error === 'board_busy') {
          set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'busy' } }))
          return
        }
        // Stays 'running' until board_run 'done' arrives via SSE, or the store-owned
        // completion watch (board-lock poll) clears it if that SSE event is missed.
        if (res.ok) _startRunWatch(key, res.run_id)
      })
      .catch(() => {
        set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' } }))
      })
  },

  decomposeFeature: (key, rigor, opts = {}) => {
    // Whole-feature decompose → sibling goals. Reuses the board-run pill state keyed by the board:
    // the run appears on the board and the pill clears via the same board_run SSE / completion watch
    // as Evaluate. Feature boards only (the /comms/features/decompose route is feature-scoped).
    const now = Date.now()
    set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'running' }, boardRunStart: { ...s.boardRunStart, [key]: now } }))
    if (key !== 'project' && key !== 'global') useProjectStore.getState().setActiveTopic(key)
    const projectRoot = useProjectStore.getState().projectPath.replace(/\\/g, '/').replace(/\/$/, '')
    apiDecomposeFeature(key, rigor, { projectRoot, adapter: opts.adapter })
      .then((res) => {
        if (res === null) { set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' } })); return }
        if (!res.ok && res.reason === 'board_busy') { set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'busy' } })); return }
        if (res.ok) {
          // 'consultation' is an FSM-flow run (holds no board-lock) → watch the runner status
          // for the board's topic; light/full are single-agent board runs (board-lock watch).
          if (rigor === 'consultation') _startFsmRunWatch(key, boardParamsForKey(key).scope)
          else _startRunWatch(key, res.run_id)
        } else set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' } }))
      })
      .catch(() => { set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' } })) })
  },

  decomposeProject: (key, rigor, opts = {}) => {
    // Whole-project decompose → sibling features, one altitude up from decomposeFeature.
    // Reuses the same board-run pill state keyed by the board: the run appears on the
    // board and the pill clears via the same board_run SSE / completion watch as Evaluate.
    // Project board only (the /comms/project/decompose route is project-scoped).
    const now = Date.now()
    set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'running' }, boardRunStart: { ...s.boardRunStart, [key]: now } }))
    const projectRoot = useProjectStore.getState().projectPath.replace(/\\/g, '/').replace(/\/$/, '')
    apiDecomposeProject(key, rigor, { projectRoot, adapter: opts.adapter })
      .then((res) => {
        if (res === null) { set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' } })); return }
        if (!res.ok && res.reason === 'board_busy') { set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'busy' } })); return }
        if (res.ok) {
          // 'consultation' is an FSM-flow run (holds no board-lock) → watch the runner status
          // for the board's topic; light/full are single-agent board runs (board-lock watch).
          if (rigor === 'consultation') _startFsmRunWatch(key, boardParamsForKey(key).scope)
          else _startRunWatch(key, res.run_id)
        } else set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' } }))
      })
      .catch(() => { set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' } })) })
  },

  markBoardRunPhase: (key, phase) => {
    if (phase === 'running') {
      const now = Date.now()
      set((s) => ({
        boardRunState: { ...s.boardRunState, [key]: 'running' },
        // Only set start time if not already running (SSE may re-emit 'running')
        boardRunStart: s.boardRunStart[key] ? s.boardRunStart : { ...s.boardRunStart, [key]: now },
      }))
    } else if (phase === 'done' || phase === 'stopped') {
      _stopRunWatch(key)
      useToastStore.getState().push(
        phase === 'done' ? 'Agent done' : 'Agent stopped',
        phase === 'done' ? 'success' : 'info',
        { category: phase === 'done' ? 'agent_done' : 'runner_state' },
      )
      set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'done' } }))
      window.setTimeout(() => {
        set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' }, boardRunStart: { ...s.boardRunStart, [key]: 0 } }))
      }, 3000)
    }
  },

  stopBoard: (key) => {
    _stopRunWatch(key)
    const params = boardParamsForKey(key)
    set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' } }))
    void apiStopBoard(params.board, params.scope)
  },

  goalRunState: {},
  goalRunStart: {},
  summaryStatus: {},

  runGoal: (goal_id, executor, opts = {}) => {
    const now = Date.now()
    set((s) => ({ goalRunState: { ...s.goalRunState, [goal_id]: 'running' }, goalRunStart: { ...s.goalRunStart, [goal_id]: now } }))

    // The project root is the PTY's working directory — without it the spawn fails
    // ("Working directory is required") and the run dies on a 30s terminal_spawn_timeout.
    // Mirror decomposeGoal / runBoard / runEvaluator, which all forward it.
    const projectRoot = useProjectStore.getState().projectPath.replace(/\\/g, '/').replace(/\/$/, '')
    apiRunGoal(goal_id, executor, { ...opts, projectRoot })
      .then((res) => {
        if (res === null) {
          set((s) => ({ goalRunState: { ...s.goalRunState, [goal_id]: 'idle' } }))
          return
        }
        if (!res.ok && res.error === 'board_busy') {
          set((s) => ({ goalRunState: { ...s.goalRunState, [goal_id]: 'busy' } }))
          return
        }
        if (!res.ok && res.error === 'not_implemented') {
          // team executor not yet available — surface via state, not by staying 'running'
          set((s) => ({ goalRunState: { ...s.goalRunState, [goal_id]: 'idle' } }))
          return
        }
        // ok=true: stay 'running'; the SSE goal_run phase drives done/idle. Only the 'single'
        // executor drains the DAG via start_board_run (board-lock held), so only it gets the
        // store-owned board-lock completion watch. loop/team run through the scheduler / FSM and
        // don't hold the board lock across the run — a board-lock poll there would false-complete,
        // so they rely on the SSE alone.
        if (res.ok && executor === 'single') _startGoalWatch(goal_id, res.run_id)
      })
      .catch(() => {
        set((s) => ({ goalRunState: { ...s.goalRunState, [goal_id]: 'idle' } }))
      })
  },

  markGoalRunPhase: (goal_id, phase) => {
    if (phase === 'running') {
      const now = Date.now()
      set((s) => ({
        goalRunState: { ...s.goalRunState, [goal_id]: 'running' },
        goalRunStart: s.goalRunStart[goal_id] ? s.goalRunStart : { ...s.goalRunStart, [goal_id]: now },
      }))
    } else if (phase === 'done' || phase === 'stopped') {
      _stopGoalWatch(goal_id)
      useToastStore.getState().push(
        phase === 'done' ? 'Goal run complete' : 'Goal run stopped',
        phase === 'done' ? 'success' : 'info',
        { category: phase === 'done' ? 'agent_done' : 'runner_state' },
      )
      set((s) => ({ goalRunState: { ...s.goalRunState, [goal_id]: 'done' } }))
      window.setTimeout(() => {
        set((s) => ({ goalRunState: { ...s.goalRunState, [goal_id]: 'idle' }, goalRunStart: { ...s.goalRunStart, [goal_id]: 0 } }))
      }, 3000)
    } else if (phase === 'error') {
      // A failed run MUST drop the elapsed timer at once — otherwise the "Decomposing…"
      // clock runs forever (the reported bug: it kept counting after the run died). Reset
      // the pill to idle and zero the start time so useElapsedProgress stops.
      _stopGoalWatch(goal_id)
      useToastStore.getState().push('Goal run failed', 'error', { category: 'runner_state' })
      set((s) => ({
        goalRunState: { ...s.goalRunState, [goal_id]: 'idle' },
        goalRunStart: { ...s.goalRunStart, [goal_id]: 0 },
      }))
    }
  },

  stopGoal: (goal_id) => {
    _stopGoalWatch(goal_id)
    set((s) => ({ goalRunState: { ...s.goalRunState, [goal_id]: 'idle' } }))
    apiStopGoal(goal_id).catch(() => undefined)
  },

  taskRunStart: {},

  runTask: (taskId, opts = {}) => {
    // The backend claims the task (task_status → in_progress) and completes it on success, so the
    // task's own status drives the card's pill/dot; taskRunStart just feeds the pill's elapsed timer.
    set((s) => ({ taskRunStart: { ...s.taskRunStart, [taskId]: Date.now() } }))
    const projectRoot = useProjectStore.getState().projectPath.replace(/\\/g, '/').replace(/\/$/, '')
    apiRunTask(taskId, { projectRoot, adapter: opts.adapter })
      .then((res) => {
        if (res && !res.ok) {
          const busy = res.reason === 'busy' || res.reason === 'board_busy' || res.reason === 'already_running'
          useToastStore.getState().push(
            busy ? 'That task is already running, or the board is busy' : "Couldn't start the task",
            busy ? 'info' : 'error',
            { category: 'runner_state' },
          )
        }
      })
      .catch(() => useToastStore.getState().push('Task run failed — server unreachable', 'error', { category: 'runner_state' }))
  },

  stopTask: (taskId) => {
    set((s) => {
      const next = { ...s.taskRunStart }
      delete next[taskId]
      return { taskRunStart: next }
    })
    apiStopTask(taskId).catch(() => undefined)
  },

  markSummaryStatus: (messageId, status, error) => {
    set((s) => ({ summaryStatus: { ...s.summaryStatus, [messageId]: status } }))
    if (status === 'ready') {
      useToastStore.getState().push('Summary ready', 'success', { category: 'db_crud' })
    } else if (status === 'failed') {
      useToastStore.getState().push(
        `Summary failed${error ? `: ${error}` : ''}`,
        'error',
        { category: 'runner_state' },
      )
    }
  },

  decomposeGoal: (goal_id, mode, opts = {}) => {
    const now = Date.now()
    // Stamp the start time immediately so the ActionPill timer ticks at t0 (mirrors runGoal /
    // runEvaluator) instead of waiting for the goal_decompose SSE 'running' phase.
    set((s) => ({
      goalRunState: { ...s.goalRunState, [goal_id]: 'running' },
      goalRunStart: { ...s.goalRunStart, [goal_id]: now },
    }))

    // Capture the project root (the PTY's working directory) and forward the chosen CLI
    // engine + optional model, mirroring runGoal / runEvaluator. Without the project root
    // the decompose agent spawned with an empty cwd and the PTY failed silently.
    const projectRoot = useProjectStore.getState().projectPath.replace(/\\/g, '/').replace(/\/$/, '')

    apiDecomposeGoal(goal_id, mode, { ...opts, projectRoot })
      .then((res) => {
        if (res === null || !res.ok) {
          // already_decomposed → the board reload will reveal the existing DAG;
          // board_busy → flag busy; otherwise just clear. Surface each so the action
          // isn't silent (the gap the unified spawn-controls pass closes).
          const next = res?.reason === 'board_busy' ? 'busy' : 'idle'
          set((s) => ({
            goalRunState: { ...s.goalRunState, [goal_id]: next },
            goalRunStart: { ...s.goalRunStart, [goal_id]: 0 },
          }))
          if (res?.reason === 'board_busy') {
            useToastStore.getState().push('Board busy — finish the running agent first', 'info', { category: 'runner_state' })
          } else if (res?.reason === 'already_decomposed') {
            useToastStore.getState().push('Goal already decomposed — showing the existing task DAG', 'info', { category: 'db_crud' })
          } else {
            useToastStore.getState().push('Decompose failed — could not start the planner', 'error', { category: 'runner_state' })
          }
          return
        }
        // ok=true: stay 'running'; the goal_decompose SSE phase drives done/idle (+ done toast).
        // planner/plan run one agent via start_board_run (board-lock held), so they get the
        // store-owned board-lock completion watch as an SSE backstop. consultation runs the FSM
        // flow (no board lock) — a board-lock poll would false-complete it — so it relies on the
        // SSE alone.
        if (mode === 'planner' || mode === 'plan') _startGoalWatch(goal_id)
      })
      .catch(() => {
        set((s) => ({ goalRunState: { ...s.goalRunState, [goal_id]: 'idle' }, goalRunStart: { ...s.goalRunStart, [goal_id]: 0 } }))
        useToastStore.getState().push('Decompose failed — server unreachable', 'error', { category: 'runner_state' })
      })
  },
}))
