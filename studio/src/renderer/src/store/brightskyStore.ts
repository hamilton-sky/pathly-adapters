import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const BRIGHTSKY_BASE_URL = 'https://brightsky-ai.onrender.com'

interface BrightskyState {
  connected: boolean
  authenticated: boolean
  accessToken: string | null
  refreshToken: string | null
  userId: string | null
  sessionId: string | null
  wsUrl: string
  authUrl: string
  authError: string | null
  setTokens: (access: string, refresh: string, user: { id: string; email: string; displayName: string }) => void
  clearAuth: () => void
  setSessionId: (id: string | null) => void
  setConnected: (val: boolean) => void
  setAuthError: (msg: string | null) => void
}

export const useBrightskyStore = create<BrightskyState>()(
  persist(
    (set) => ({
      connected: false,
      authenticated: false,
      accessToken: null,
      refreshToken: null,
      userId: null,
      sessionId: null,
      wsUrl: `${BRIGHTSKY_BASE_URL}/ws`,
      authUrl: `${BRIGHTSKY_BASE_URL}/auth/google`,
      authError: null,

      setTokens: (access, refresh, user) =>
        set({
          accessToken: access,
          refreshToken: refresh,
          userId: user.id,
          authenticated: true,
          connected: true,
          authError: null,
        }),

      clearAuth: () =>
        set({
          accessToken: null,
          refreshToken: null,
          userId: null,
          sessionId: null,
          authenticated: false,
          connected: false,
          authError: null,
        }),

      setSessionId: (id) => set({ sessionId: id }),

      setConnected: (val) => set({ connected: val }),

      setAuthError: (msg) => set({ authError: msg }),
    }),
    {
      name: 'brightsky-store',
      partialize: (s) => ({
        accessToken: s.accessToken,
        refreshToken: s.refreshToken,
        userId: s.userId,
        authenticated: s.authenticated,
      }),
    }
  )
)
