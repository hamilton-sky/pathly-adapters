import { create } from 'zustand'
import type { Boards, Feature, Message, BoardScope, MessageType, FeatureStatus, Stage } from '../components/CommandCenter/types'
import {
  fetchBoard,
  apiPost,
  apiAnswer,
  apiAcknowledge,
  apiToggleScope,
  apiDelete,
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
} from './commsApi'
import { listDirs } from '../services/pathlyApi'
import { useRunnerStore } from './runnerStore'
import { useProjectStore } from './projectStore'

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
  /** Retract one of your own messages — only while no agent has read it. */
  deleteMessage: (key: string, messageId: string) => void

  // GAP 4 — management actions + transient search overlay state.
  searchResults: Message[] | null
  searchTerm: string
  runSearch: (key: string, query: string) => Promise<void>
  clearSearch: () => void
  supersede: (key: string, oldId: string, newId: string) => void
  attach: (key: string, messageId: string, path: string, atype?: Message['atype']) => void

  // C2 — single-agent run state keyed by board (e.g. feature id, 'project', 'global')
  boardRunState: Record<string, 'idle' | 'running' | 'busy' | 'done'>
  runSingleAgent: (key: string, instructions: string, agent?: string, skill?: string, interactive?: boolean) => void
  stopBoard: (key: string) => void
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
      const plansDir = `${projectPath}/pathly/plans`
      const names = await listDirs(plansDir).catch(() => [] as string[])
      const filtered = names.filter((n) => n !== '.archive')
      // Enrich each feature from its STATE.json (stage + conv) and feedback/ (blocked).
      const features: Feature[] = await Promise.all(
        filtered.map(async (id) => {
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
    const params = scopeToParams(scope, key)

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
    set((s) => {
      const arr = s.boards[key] || []
      const m = arr.find((x) => x.id === messageId)
      if (!m || m.from !== 'you' || m.readByAgent) return s
      return { boards: { ...s.boards, [key]: arr.filter((x) => x.id !== messageId) } }
    })
    apiDelete(messageId).catch(() => { /* best-effort */ })
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

  runSingleAgent: (key, instructions, agent, skill, interactive) => {
    set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'running' } }))

    const isFeature = key !== 'project' && key !== 'global'
    const scope: BoardScope = isFeature ? 'feature' : key as BoardScope
    const params = scopeToParams(scope, key)
    const projectRoot = isFeature ? undefined
      : useProjectStore.getState().projectPath.replace(/\\/g, '/').replace(/\/$/, '')

    apiRunBoard(params.board, params.scope, 'single-agent', instructions, projectRoot, agent, skill, interactive)
      .then((res) => {
        if (res === null) {
          set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' } }))
          return
        }
        if (!res.ok && res.error === 'board_busy') {
          set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'busy' } }))
          return
        }
        set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'done' } }))
        // Reset to idle after a short display window
        window.setTimeout(() => {
          set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' } }))
        }, 3000)
      })
      .catch(() => {
        set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' } }))
      })
  },

  stopBoard: (key) => {
    const isFeature = key !== 'project' && key !== 'global'
    const scope: BoardScope = isFeature ? 'feature' : key as BoardScope
    const params = scopeToParams(scope, key)
    set((s) => ({ boardRunState: { ...s.boardRunState, [key]: 'idle' } }))
    void apiStopBoard(params.board, params.scope)
  },
}))
