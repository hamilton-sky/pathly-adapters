import { create } from 'zustand'
import type { MatchResult } from '../types/chat'

export type { MatchResult }

/** One section of the HQ board-context packet (hq-copilot ticket 06). */
export interface HqContextSection {
  name: string
  included: boolean
  cut_reason: string | null
  /** Estimated tokens the section took (or would have, when cut over budget);
   *  0 when it was not read. Absent from older servers. */
  tokens?: number
}

/** The context manifest shown under an HQ answer — read-only display backed
 *  by GET /hq/context. `unavailable` renders the amber note instead. */
export interface HqContextManifest {
  /** The board the packet was built for — shown on the context line. */
  board: string
  tokens_est: number
  budget: number
  sections: HqContextSection[]
  model: string
  eligible_model: boolean
  unavailable: boolean
  /** Operator actions the turn offered the model (none: read-only). */
  actions?: string[]
}

/** Where an HQ operator card stands. `proposed` shows Run/Cancel; every other
 *  status is a one-line record. */
export type HqActionStatus = 'proposed' | 'running' | 'done' | 'failed' | 'cancelled' | 'stale' | 'invalid' | 'unavailable'

/** A confirm card for one action the local model proposed (POST /hq/actions/check). */
export interface HqActionCard {
  id: string
  name: string
  label: string
  /** In words: "changes state", "spends $", "hard to undo". */
  risk: string[]
  runs_on: 'server' | 'studio'
  args: Record<string, unknown>
  /** Verb + target: "Pause run goal-x (team · BUILDING)". */
  title: string
  status: HqActionStatus
  /** The state the user saw — the server compares it at the click. */
  fingerprint: string
  summary?: string
  board: string
  projectRoot: string | null
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  thinking?: string
  status: 'idle' | 'streaming' | 'done'
  tokens?: number
  mode?: 'chat' | 'automation'
  source?: string
  /** Attached after a local-model (HQ) answer completes; drives the
   *  collapsible context manifest. Absent for other sources. */
  contextManifest?: HqContextManifest
  /** HQ operator: the actions this answer proposed, in order. */
  actionCards?: HqActionCard[]
  automationPlan?: {
    intent: string
    steps: import('../types/automation').AutomationStep[]
  }
}

export type TerminalKind = 'claude' | 'codex' | 'shell' | 'antigravity'

export interface TargetOutput {
  lines: string[]
  running: boolean
}

export interface ChatState {
  messages: Message[]
  isLoading: boolean
  /** Which terminal target the Run button writes to */
  targetKind: TerminalKind
  /** Per-target PTY output — both claude and codex tracked independently */
  outputByTarget: Record<TerminalKind, TargetOutput>
  currentMatch: MatchResult | null
  autoApprove: boolean
  altMatches: MatchResult[]
  isEmbedding: boolean
  embedReady: boolean
  embedProgress: number   // 0–100 while model downloads, 100 when ready
  chatMode: 'llm' | 'claude'

  // ── message actions ──────────────────────────────────────
  addMessage: (msg: Message) => void
  updateLastMessage: (patch: Partial<Message>) => void
  /** Patch one message by id; a no-op when it is gone (chat cleared or switched). */
  updateMessage: (id: string, patch: Partial<Message>) => void
  /** Replace the whole conversation (opening a saved HQ chat). */
  setMessages: (messages: Message[]) => void
  clearMessages: () => void
  setLoading: (b: boolean) => void

  // ── target / output actions ───────────────────────────────
  setTargetKind: (kind: TerminalKind) => void
  appendOutputLine: (kind: TerminalKind, line: string) => void
  clearOutputLines: (kind?: TerminalKind) => void
  setCommandRunning: (kind: TerminalKind, b: boolean) => void

  // ── match actions ─────────────────────────────────────────
  setCurrentMatch: (match: MatchResult | null) => void
  setAutoApprove: (b: boolean) => void
  setAltMatches: (matches: MatchResult[]) => void
  setIsEmbedding: (b: boolean) => void
  setEmbedReady: (b: boolean) => void
  setEmbedProgress: (n: number) => void
  setChatMode: (mode: 'llm' | 'claude') => void
}

const emptyTarget = (): TargetOutput => ({ lines: [], running: false })

export const useChatStore = create<ChatState>()((set) => ({
  messages: [],
  isLoading: false,
  targetKind: 'claude',
  outputByTarget: { claude: emptyTarget(), codex: emptyTarget(), shell: emptyTarget(), antigravity: emptyTarget() },
  currentMatch: null,
  autoApprove: false,
  altMatches: [],
  isEmbedding: false,
  embedReady: false,
  embedProgress: 0,
  chatMode: 'llm',

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

  updateLastMessage: (patch) =>
    set((s) => {
      if (s.messages.length === 0) return {}
      const messages = [...s.messages]
      messages[messages.length - 1] = { ...messages[messages.length - 1], ...patch }
      return { messages }
    }),

  updateMessage: (id, patch) =>
    set((s) => {
      const i = s.messages.findIndex((m) => m.id === id)
      if (i === -1) return {}
      const messages = [...s.messages]
      messages[i] = { ...messages[i], ...patch }
      return { messages }
    }),

  setMessages: (messages) => set({ messages }),

  clearMessages: () => set({ messages: [] }),

  setLoading: (b) => set({ isLoading: b }),

  setTargetKind: (kind) => set({ targetKind: kind }),

  appendOutputLine: (kind, line) =>
    set((s) => ({
      outputByTarget: {
        ...s.outputByTarget,
        [kind]: {
          ...s.outputByTarget[kind],
          lines: [...s.outputByTarget[kind].lines, line].slice(-200),
        },
      },
    })),

  clearOutputLines: (kind) =>
    set((s) => {
      if (kind) {
        return {
          outputByTarget: {
            ...s.outputByTarget,
            [kind]: emptyTarget(),
          },
        }
      }
      return { outputByTarget: { claude: emptyTarget(), codex: emptyTarget(), shell: emptyTarget(), antigravity: emptyTarget() } }
    }),

  setCommandRunning: (kind, b) =>
    set((s) => ({
      outputByTarget: {
        ...s.outputByTarget,
        [kind]: { ...s.outputByTarget[kind], running: b },
      },
    })),

  setCurrentMatch: (match) => set({ currentMatch: match }),
  setAutoApprove: (b) => set({ autoApprove: b }),
  setAltMatches: (matches) => set({ altMatches: matches }),
  setIsEmbedding: (b) => set({ isEmbedding: b }),
  setEmbedReady: (b) => set({ embedReady: b }),
  setEmbedProgress: (n) => set({ embedProgress: n }),
  setChatMode: (mode) => set({ chatMode: mode }),
}))
