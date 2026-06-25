import { create } from 'zustand'
import type { Boards, Feature, Message, BoardScope, MessageType, FeatureStatus, Stage } from '../components/CommandCenter/types'
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
  apiSearch,
  apiSupersede,
  apiAttach,
  apiRunBoard,
  apiStopBoard,
  apiRunGoal,
  apiStopGoal,
  apiDecomposeGoal,
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

  // GAP 4 — management actions + transient search overlay state.
  searchResults: Message[] | null
  searchTerm: string
  runSearch: (key: string, query: string) => Promise<void>
  clearSearch: () => void
  supersede: (key: string, oldId: string, newId: string) => void
  attach: (key: string, messageId: string, path: string, atype?: Message['atype']) => void

  // C2 — single-agent run state keyed by board (e.g. feature id, 'project', 'global')
  boardRunState: Record<string, 'idle' | 'running' | 'busy' | 'done'>
  /** Epoch ms when the board run started — drives the elapsed clock in RunPill. */
  boardRunStart: Record<string, number>
  runSingleAgent: (key: string, opts: { agent?: string; skill?: string; systemPrompt?: string; interactive?: boolean; adapter?: string; instructions?: string; progress?: string }) => void
  /** Run the evaluator on a board: classify its content and propose concrete tasks.
   *  `systemPrompt` carries the optional evaluation lens; `instructions` carries
   *  the optional extra-instructions box. */
  runEvaluator: (key: string, opts?: { adapter?: string; systemPrompt?: string; instructions?: string }) => void
  /** Update a board's run state from a board_run SSE phase (running/done/stopped). */
  markBoardRunPhase: (key: string, phase: string) => void
  stopBoard: (key: string) => void

  // Goal DAG run state keyed by goal message id
  goalRunState: Record<string, 'idle' | 'running' | 'busy' | 'done'>
  /** Epoch ms when the goal run started — drives the elapsed clock in RunPill. */
  goalRunStart: Record<string, number>
  runGoal: (goal_id: string, executor?: string, opts?: RunGoalOpts) => void
  /** Decompose a goal into a task DAG (planner = fast, consultation = deep). */
  decomposeGoal: (goal_id: string, mode: DecomposeMode, opts?: { adapter?: string; model?: string }) => void
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
    set((s) => ({ boards: { ...s.boards, [boardId]: messages } }))
  },

  loadFeatures: async (projectPath: string) => {
    try {
      // Legacy features live under pathly/plans/<id>/
      const plansDir = `${projectPath}/pathly/plans`
      const legacyNames = await listDirs(plansDir).catch(() => [] as string[])
      const legacyIds = legacyNames.filter((n) => n !== '.archive')

      // New-style features live directly under pathly/<id>/
      // Exclude reserved names so we don't pick up "plans" or hidden dirs.
      const RESERVED = new Set(['plans', '.archive'])
      const pathlyDir = `${projectPath}/pathly`
      const topLevelNames = await listDirs(pathlyDir).catch(() => [] as string[])
      const newStyleIds = topLevelNames.filter((n) => !RESERVED.has(n))

      // Merge: new-style takes precedence; legacy ids not already covered are appended.
      const seen = new Set(newStyleIds)
      const allIds = [...newStyleIds, ...legacyIds.filter((id) => !seen.has(id))]

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
      time: 'now',
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

  searchResults: null,
  searchTerm: '',

  runSearch: async (key, query) => {
    const q = query.trim()
    if (!q) { set({ searchResults: null, searchTerm: '' }); return }
    set({ searchTerm: q })
    const isFeature = key !== 'project' && key !== 'global'
    const scope: BoardScope = isFeature ? 'feature' : key as BoardScope
    const params = scopeToParams(scope, key)
    const feature = isFeature ? key : (scope === 'global' ? 'global' : key)
    const results = await apiSearch(q, feature, params.board, params.scope)
    set({ searchResults: results })
  },

  clearSearch: () => set({ searchResults: null, searchTerm: '' }),

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
    const scope: BoardScope = isFeature ? 'feature' : key as BoardScope
    const params = scopeToParams(scope, key)
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
        // The run clears when the board_run 'done'/'stopped' phase arrives over the
        // comms SSE → markBoardRunPhase. (No auto-flip to done on the start ack.)
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
    const scope: BoardScope = isFeature ? 'feature' : key as BoardScope
    const params = scopeToParams(scope, key)
    const projectRoot = useProjectStore.getState().projectPath.replace(/\\/g, '/').replace(/\/$/, '')

    apiRunBoard(params.board, params.scope, 'evaluator', { projectRoot, ...opts })
      .then((res) => {
        if (res === null) {
          set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' } }))
          return
        }
        if (!res.ok && res.error === 'board_busy') {
          set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'busy' } }))
        }
        // Otherwise stays 'running' until the board_run 'done' phase arrives via SSE.
      })
      .catch(() => {
        set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' } }))
      })
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
    const isFeature = key !== 'project' && key !== 'global'
    const scope: BoardScope = isFeature ? 'feature' : key as BoardScope
    const params = scopeToParams(scope, key)
    set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' } }))
    void apiStopBoard(params.board, params.scope)
  },

  goalRunState: {},
  goalRunStart: {},
  summaryStatus: {},

  runGoal: (goal_id, executor, opts = {}) => {
    const now = Date.now()
    set((s) => ({ goalRunState: { ...s.goalRunState, [goal_id]: 'running' }, goalRunStart: { ...s.goalRunStart, [goal_id]: now } }))

    apiRunGoal(goal_id, executor, opts)
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
        // ok=true: stay 'running'; SSE goal_run phase drives the transition to done/idle
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
      useToastStore.getState().push(
        phase === 'done' ? 'Goal run complete' : 'Goal run stopped',
        phase === 'done' ? 'success' : 'info',
        { category: phase === 'done' ? 'agent_done' : 'runner_state' },
      )
      set((s) => ({ goalRunState: { ...s.goalRunState, [goal_id]: 'done' } }))
      window.setTimeout(() => {
        set((s) => ({ goalRunState: { ...s.goalRunState, [goal_id]: 'idle' }, goalRunStart: { ...s.goalRunStart, [goal_id]: 0 } }))
      }, 3000)
    }
  },

  stopGoal: (goal_id) => {
    set((s) => ({ goalRunState: { ...s.goalRunState, [goal_id]: 'idle' } }))
    apiStopGoal(goal_id).catch(() => undefined)
  },

  markSummaryStatus: (messageId, status, error) => {
    set((s) => ({ summaryStatus: { ...s.summaryStatus, [messageId]: status } }))
    if (status === 'ready') {
      useToastStore.getState().push('📝 Summary ready', 'success', { category: 'db_crud' })
    } else if (status === 'failed') {
      useToastStore.getState().push(
        `⚠ Summary failed${error ? `: ${error}` : ''}`,
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
      })
      .catch(() => {
        set((s) => ({ goalRunState: { ...s.goalRunState, [goal_id]: 'idle' }, goalRunStart: { ...s.goalRunStart, [goal_id]: 0 } }))
        useToastStore.getState().push('Decompose failed — server unreachable', 'error', { category: 'runner_state' })
      })
  },
}))
