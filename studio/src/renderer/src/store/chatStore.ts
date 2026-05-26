import { create } from 'zustand'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  status: 'idle' | 'streaming' | 'done'
  tokens?: number
}

export type MatchState = {
  skill: string
  confidence: number
  command: string
} | null

export interface MatchResult {
  skill: string
  confidence: number
  command: string
}

export interface ChatState {
  messages: Message[]
  matchState: MatchState
  isLoading: boolean
  targetKind: 'claude' | 'codex'
  outputLines: string[]
  currentMatch: MatchResult | null
  addMessage: (msg: Message) => void
  updateLastMessage: (patch: Partial<Message>) => void
  clearMessages: () => void
  setMatchState: (ms: MatchState) => void
  setLoading: (b: boolean) => void
  setTargetKind: (kind: 'claude' | 'codex') => void
  appendOutputLine: (line: string) => void
  clearOutputLines: () => void
  setCurrentMatch: (match: MatchResult | null) => void
}

export const useChatStore = create<ChatState>()((set) => ({
  messages: [],
  matchState: null,
  isLoading: false,
  targetKind: 'claude',
  outputLines: [],
  currentMatch: null,

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

  updateLastMessage: (patch) =>
    set((s) => {
      if (s.messages.length === 0) return {}
      const messages = [...s.messages]
      messages[messages.length - 1] = { ...messages[messages.length - 1], ...patch }
      return { messages }
    }),

  clearMessages: () => set({ messages: [] }),

  setMatchState: (ms) => set({ matchState: ms }),

  setLoading: (b) => set({ isLoading: b }),

  setTargetKind: (kind) => set({ targetKind: kind }),

  appendOutputLine: (line) =>
    set((s) => ({ outputLines: [...s.outputLines, line].slice(-5) })),

  clearOutputLines: () => set({ outputLines: [] }),

  setCurrentMatch: (match) => set({ currentMatch: match }),
}))
