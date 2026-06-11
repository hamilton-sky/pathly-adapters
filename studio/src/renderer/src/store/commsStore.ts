import { create } from 'zustand'
import type { Boards, Feature, Message, BoardScope, MessageType, FeatureStatus, Stage } from '../components/HQ/CommandCenter/types'
import {
  fetchBoard,
  apiPost,
  apiAnswer,
  apiAcknowledge,
  apiToggleScope,
  apiDelete,
  scopeToParams,
  buildFeature,
} from './commsApi'
import { listDirs } from '../services/pathlyApi'

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
  resolve: (messageId: string, mode: 'block' | 'note' | 'ignore') => void
  setFeatureStatus: (featureId: string, status: FeatureStatus, stage?: Stage) => void
  toggleScope: (featureId: string, scope: BoardScope, projectRoot: string) => void
  /** Retract one of your own messages — only while no agent has read it. */
  deleteMessage: (key: string, messageId: string) => void
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
      const features: Feature[] = filtered.map(buildFeature)
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

  resolve: (mid, mode) => {
    // TODO: full FSM block/note/ignore semantics — POST /comms/acknowledge covers the
    // acknowledge path; block→RETRY and note→decision-post require additional FSM calls
    // that are out of scope for this wiring task.
    set((s) => {
      const key = Object.keys(s.boards).find((k) => (s.boards[k] || []).some((m) => m.id === mid))
      if (!key) return s
      const resolution =
        mode === 'block' ? 'blocked → RETRY (builder)'
        : mode === 'note' ? 'noted as v2 → REVIEWING advances'
        : 'ignored → REVIEWING advances'
      const arr = (s.boards[key] || []).map((m) =>
        m.id === mid ? { ...m, status: 'resolved' as const, resolution } : m)
      const newStatus: FeatureStatus = 'running'
      const newStage: Stage = mode === 'block' ? 'BUILDING' : 'TESTING'
      const features = s.features.map((f) =>
        f.id === key ? { ...f, status: newStatus, stage: newStage } : f)
      return { boards: { ...s.boards, [key]: arr }, features }
    })

    apiAcknowledge(mid, 'you').catch(() => { /* best-effort */ })
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
}))
