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

export interface ChatState {
  messages: Message[]
  isLoading: boolean
  isCommandRunning: boolean
  targetKind: 'claude' | 'codex'
  outputLines: string[]
  currentMatch: MatchResult | null
  autoApprove: boolean
  altMatches: MatchResult[]
  isEmbedding: boolean
  embedReady: boolean
  addMessage: (msg: Message) => void
  updateLastMessage: (patch: Partial<Message>) => void
  clearMessages: () => void
  setLoading: (b: boolean) => void
  setCommandRunning: (b: boolean) => void
  setTargetKind: (kind: 'claude' | 'codex') => void
  appendOutputLine: (line: string) => void
  clearOutputLines: () => void
  setCurrentMatch: (match: MatchResult | null) => void
  setAutoApprove: (b: boolean) => void
  setAltMatches: (matches: MatchResult[]) => void
  setIsEmbedding: (b: boolean) => void
  setEmbedReady: (b: boolean) => void
}

export const useChatStore = create<ChatState>()((set) => ({
  messages: [],
  isLoading: false,
  isCommandRunning: false,
  targetKind: 'claude',
  outputLines: [],
  currentMatch: null,
  autoApprove: false,
  altMatches: [],
  isEmbedding: false,
  embedReady: false,

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

  setCommandRunning: (b) => set({ isCommandRunning: b }),

  setTargetKind: (kind) => set({ targetKind: kind }),

  appendOutputLine: (line) =>
    set((s) => ({ outputLines: [...s.outputLines, line].slice(-200) })),

  clearOutputLines: () => set({ outputLines: [] }),

  setCurrentMatch: (match) => set({ currentMatch: match }),

  setAutoApprove: (b) => set({ autoApprove: b }),
  setAltMatches: (matches) => set({ altMatches: matches }),
  setIsEmbedding: (b) => set({ isEmbedding: b }),
  setEmbedReady: (b) => set({ embedReady: b }),
}))
