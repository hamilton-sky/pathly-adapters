import { create } from 'zustand'
import type { Boards, Feature, Message, BoardScope, MessageType, FeatureStatus, Stage } from '../components/HQ/CommandCenter/types'

// TODO: wire to GET /comms?feature=&board= — replace SEED_* with a fetch on mount
// TODO: live updates via GET /events/comms?scope= (SSE COMMS_UPDATE → appendMessage)

// ── Seed data (dev/preview only) ────────────────────────────────────
let _n = 0
const nextId = () => `m${++_n}`

const SEED_FEATURES: Feature[] = [
  { id: 'send-to-agent-diff', stage: 'BUILDING', conv: 3, status: 'running', agent: 'builder',
    last: 'builder: phases 7–9 complete. Wiring DiffViewer scroll sync.',
    scope: { feature: true, project: true, global: true } },
  { id: 'comms-board', stage: 'PLANNING', conv: 1, status: 'idle', agent: 'architect',
    last: 'architect: drafting comms_messages + sqlite-vec schema.',
    scope: { feature: true, project: true, global: true } },
  { id: 'event-phase-summary', stage: 'REVIEWING', conv: 2, status: 'blocked', agent: 'reviewer',
    last: 'reviewer: 3 failures — missing null guards in summary writer.',
    scope: { feature: true, project: true, global: false } },
  { id: 'otel-export-cli', stage: 'DONE', conv: 4, status: 'done', agent: 'retro',
    last: 'retro: archived. 64.8k tok · $3.64 · 6m 29s.',
    scope: { feature: true, project: true, global: true } },
]

const SEED_BOARDS: Boards = {
  'send-to-agent-diff': [
    { id: nextId(), type: 'decision', from: 'you', stage: 'REVIEWING', time: '2h', pinned: true,
      text: 'Skip rename detection — that is v2 scope.' },
    { id: nextId(), type: 'status', from: 'builder', stage: 'BUILDING', time: '8m',
      text: 'Phases 7–9 complete. `DiffViewer.tsx` created. Starting scroll-sync.' },
    { id: nextId(), type: 'discovery', from: 'builder', stage: 'BUILDING', time: '6m',
      text: 'Virtual scroll is needed when a diff exceeds ~500 lines, or the panes jank.' },
    { id: nextId(), type: 'question', from: 'builder', stage: 'BUILDING', time: '4m', status: 'pending',
      text: 'Two approaches for scroll sync between the diff panes. Preference?',
      options: [
        { id: 'a', label: 'CSS scroll-snap', desc: 'simple, native' },
        { id: 'b', label: 'JS IntersectionObserver', desc: 'more control' },
      ] },
  ],
  'comms-board': [
    { id: nextId(), type: 'decision', from: 'you', stage: 'PLANNING', time: '1h', pinned: true,
      text: 'Embeddings: `all-MiniLM-L6-v2`, 384-dim. No external API cost.' },
    { id: nextId(), type: 'status', from: 'architect', stage: 'PLANNING', time: '12m',
      text: 'Schema drafted: `comms_messages` + `comms_embeddings` (vec0).' },
  ],
  'event-phase-summary': [
    { id: nextId(), type: 'warning', from: 'reviewer', stage: 'REVIEWING', time: '3m', status: 'open',
      text: 'Rename detection missing and 2 null-guard failures in the summary writer.' },
  ],
  'otel-export-cli': [
    { id: nextId(), type: 'status', from: 'retro', stage: 'RETRO', time: '1d',
      text: 'Run archived. Lessons written to `pathly/lessons/`.' },
  ],
  project: [
    { id: nextId(), type: 'decision', from: 'you', time: '4d', pinned: true, text: 'Use `shadcn/ui` for all new components.' },
    { id: nextId(), type: 'decision', from: 'you', time: '4d', pinned: true, text: 'Auth is handled by `/lib/auth.ts` — never roll custom auth.' },
    { id: nextId(), type: 'decision', from: 'you', time: '6d', pinned: true, text: 'TypeScript `strict` mode across the repo.' },
    { id: nextId(), type: 'artifact', from: 'you', time: '3d', artifact: 'ARCHITECTURE.md', atype: 'md',
      text: 'Adapter surfaces per host, deployment structure, host detection, installed manifests…' },
    { id: nextId(), type: 'status', from: 'reviewer', stage: 'REVIEWING', time: '20m',
      text: 'Found 2 issues in `event-phase-summary`; surfaced to its board.' },
  ],
  global: [
    { id: nextId(), type: 'decision', from: 'you', time: '2w', pinned: true, text: 'Use `Zod` for all schema validation.' },
    { id: nextId(), type: 'decision', from: 'you', time: '3w', pinned: true, text: 'No class components anywhere in the org.' },
    { id: nextId(), type: 'decision', from: 'you', time: '5w', pinned: true, text: 'All user-facing errors must include an error code.' },
    { id: nextId(), type: 'artifact', from: 'you', time: '5w', artifact: 'auth-pattern.ts', atype: 'code',
      text: 'export async function withAuth(req: Request) { /* always use this pattern */ }' },
  ],
}

function cloneBoards(b: Boards): Boards {
  const out: Boards = {}
  // Seed history is treated as already read by agents → not retractable. Only
  // messages you post live (readByAgent: false) can be deleted.
  for (const k of Object.keys(b)) {
    out[k] = b[k].map((m) => ({ ...m, readByAgent: m.from === 'you' ? true : m.readByAgent }))
  }
  return out
}

function isPending(m: Message): boolean {
  return (m.type === 'question' && m.status === 'pending')
    || (m.type === 'warning' && m.status === 'open')
    || m.type === 'escalation'
}

// ── Store shape ──────────────────────────────────────────────────────

export interface CommsState {
  features: Feature[]
  boards: Boards

  pendingCount: (featureId: string) => number
  messagesFor: (scope: BoardScope, mainFeature: string) => Message[]
  appendMessage: (key: string, message: Message) => void

  post: (key: string, type: MessageType, text: string, stage?: Stage | null) => string
  answer: (featureId: string, messageId: string, optionId: string) => void
  resolve: (messageId: string, mode: 'block' | 'note' | 'ignore') => void
  setFeatureStatus: (featureId: string, status: FeatureStatus, stage?: Stage) => void
  toggleScope: (featureId: string, scope: BoardScope) => void  // TODO: POST /comms/scope
  /** Retract one of your own messages — only while no agent has read it. */
  deleteMessage: (key: string, messageId: string) => void
}

export const useCommsStore = create<CommsState>()((set, get) => ({
  features: SEED_FEATURES.map((f) => ({ ...f })),
  boards: cloneBoards(SEED_BOARDS),

  pendingCount: (fid) => (get().boards[fid] || []).filter(isPending).length,

  messagesFor: (scope, mainFeature) =>
    get().boards[scope === 'feature' ? mainFeature : scope] || [],

  appendMessage: (key, message) =>
    set((s) => ({ boards: { ...s.boards, [key]: [...(s.boards[key] || []), message] } })),

  post: (key, type, text, stage) => {
    const m: Message = {
      id: nextId(), type, from: 'you', time: 'now', text,
      stage: stage ?? null, pinned: type === 'decision', readByAgent: false,
      ...(type === 'question'
        ? { status: 'pending', options: [{ id: 'a', label: 'Option A' }, { id: 'b', label: 'Option B' }] }
        : {}),
    }
    // TODO: POST /comms/post — optimistic append, reconcile on echo
    set((s) => ({ boards: { ...s.boards, [key]: [...(s.boards[key] || []), m] } }))
    return m.id
  },

  answer: (fid, mid, opt) => {
    // TODO: POST /comms/answer
    set((s) => {
      const arr = s.boards[fid] || []
      const q = arr.find((m) => m.id === mid)
      if (!q || q.status === 'answered') return s
      const chosen = (q.options || []).find((o) => o.id === opt)
      const next = arr.map((m) => (m.id === mid ? { ...m, status: 'answered' as const, answer: opt } : m))
      next.push({
        id: nextId(), type: 'answer', from: 'you', stage: q.stage, time: 'now',
        text: `Use \`${chosen?.label}\`. Keep it simple.`,
      })
      next.push({
        id: nextId(), type: 'status', from: 'builder', stage: q.stage, time: 'now', ack: true,
        text: `Got it — implementing \`${chosen?.label}\`.`,
      })
      return { boards: { ...s.boards, [fid]: next } }
    })
  },

  resolve: (mid, mode) => {
    // TODO: POST /comms/acknowledge + POST /comms/post (decision) on mode === 'note'
    set((s) => {
      const key = Object.keys(s.boards).find((k) => (s.boards[k] || []).some((m) => m.id === mid))
      if (!key) return s
      const resolution =
        mode === 'block' ? 'blocked → RETRY (builder)'
        : mode === 'note' ? 'noted as v2 → REVIEWING advances'
        : 'ignored → REVIEWING advances'
      const arr = (s.boards[key] || []).map((m) =>
        m.id === mid ? { ...m, status: 'resolved' as const, resolution } : m)
      if (mode === 'note') {
        arr.push({
          id: nextId(), type: 'decision', from: 'you', stage: 'REVIEWING', time: 'now', pinned: true,
          text: 'Rename detection is v2 scope. Do not block.',
        })
      }
      const newStatus: FeatureStatus = 'running'
      const newStage: Stage = mode === 'block' ? 'BUILDING' : 'TESTING'
      const features = s.features.map((f) =>
        f.id === key ? { ...f, status: newStatus, stage: newStage } : f)
      return { boards: { ...s.boards, [key]: arr }, features }
    })
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

  toggleScope: (fid, scope) => {
    // TODO: GET/POST /comms/scope — endpoint not yet exposed over HTTP; see PORTING-MAP §4
    set((s) => ({
      features: s.features.map((f) =>
        f.id === fid ? { ...f, scope: { ...f.scope, [scope]: !f.scope[scope] } } : f),
    }))
  },

  deleteMessage: (key, messageId) =>
    // TODO: live → POST /comms/delete (soft-trash); the server rejects once read_by is non-empty.
    set((s) => {
      const arr = s.boards[key] || []
      const m = arr.find((x) => x.id === messageId)
      if (!m || m.from !== 'you' || m.readByAgent) return s  // only your own, still-unread
      return { boards: { ...s.boards, [key]: arr.filter((x) => x.id !== messageId) } }
    }),
}))
