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

export interface ChatState {
  messages: Message[]
  matchState: MatchState
  isLoading: boolean
  addMessage: (msg: Message) => void
  updateLastMessage: (patch: Partial<Message>) => void
  clearMessages: () => void
  setMatchState: (ms: MatchState) => void
  setLoading: (b: boolean) => void
}

export const useChatStore = create<ChatState>()((set) => ({
  messages: [],
  matchState: null,
  isLoading: false,

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
}))
