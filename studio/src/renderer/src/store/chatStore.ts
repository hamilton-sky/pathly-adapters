import { create } from 'zustand'
import type { MatchResult } from '../types/chat'

export type { MatchResult }

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  status: 'idle' | 'streaming' | 'done'
  tokens?: number
}

export type TerminalKind = 'claude' | 'codex'

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

  // ── message actions ──────────────────────────────────────
  addMessage: (msg: Message) => void
  updateLastMessage: (patch: Partial<Message>) => void
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
}

const emptyTarget = (): TargetOutput => ({ lines: [], running: false })

export const useChatStore = create<ChatState>()((set) => ({
  messages: [],
  isLoading: false,
  targetKind: 'claude',
  outputByTarget: { claude: emptyTarget(), codex: emptyTarget() },
  currentMatch: null,
  autoApprove: false,
  altMatches: [],
  isEmbedding: false,
  embedReady: false,
  embedProgress: 0,

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

  updateLastMessage: (patch) =>
    set((s) => {
      if (s.messages.length === 0) return {}
      const messages = [...s.messages]
      messages[messages.length - 1] = { ...messages[messages.length - 1], ...patch }
      return { messages }
    }),

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
      return { outputByTarget: { claude: emptyTarget(), codex: emptyTarget() } }
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
}))
