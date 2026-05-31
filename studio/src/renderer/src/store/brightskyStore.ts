import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// Read from Vite env if present (set VITE_BRIGHTSKY_URL in studio/.env.local for local dev)
// Default: Render production backend
export const BRIGHTSKY_BASE_URL: string =
  (import.meta.env.VITE_BRIGHTSKY_URL as string | undefined) || 'https://bright-sky-ai.onrender.com'

// WS URL: explicit override first, otherwise derived from base (https→wss, http→ws).
// Local dev needs an explicit override because the WS port (3002) differs from HTTP (3001).
export const BRIGHTSKY_WS_URL: string =
  (import.meta.env.VITE_BRIGHTSKY_WS_URL as string | undefined) ||
  BRIGHTSKY_BASE_URL.replace(/^https:\/\//, 'wss://').replace(/^http:\/\//, 'ws://') + '/ws'

interface BrightskyState {
  connected: boolean
  authenticated: boolean
  thinkingLabel: string | null
  accessToken: string | null
  refreshToken: string | null
  userId: string | null
  userEmail: string | null
  userDisplayName: string | null
  sessionId: string | null
  wsUrl: string
  authUrl: string
  authError: string | null
  setTokens: (access: string, refresh: string, user: { id: string; email: string; displayName: string }) => void
  clearAuth: () => void
  setSessionId: (id: string | null) => void
  setConnected: (val: boolean) => void
  setAuthError: (msg: string | null) => void
  setThinkingLabel: (label: string | null) => void
}

export const useBrightskyStore = create<BrightskyState>()(
  persist(
    (set) => ({
      connected: false,
      authenticated: false,
      thinkingLabel: null,
      accessToken: null,
      refreshToken: null,
      userId: null,
      userEmail: null,
      userDisplayName: null,
      sessionId: null,
      wsUrl: BRIGHTSKY_WS_URL,
      authUrl: `${BRIGHTSKY_BASE_URL}/auth/google`,
      authError: null,

      setTokens: (access, refresh, user) =>
        set({
          accessToken: access,
          refreshToken: refresh,
          userId: user.id,
          userEmail: user.email,
          userDisplayName: user.displayName,
          authenticated: true,
          // NOTE: do NOT set connected:true here — that is set only by ws.onopen
          authError: null,
        }),

      clearAuth: () =>
        set({
          accessToken: null,
          refreshToken: null,
          userId: null,
          userEmail: null,
          userDisplayName: null,
          sessionId: null,
          authenticated: false,
          connected: false,
          authError: null,
        }),

      setSessionId: (id) => set({ sessionId: id }),

      setConnected: (val) => set({ connected: val }),

      setAuthError: (msg) => set({ authError: msg }),
      setThinkingLabel: (label) => set({ thinkingLabel: label }),
    }),
    {
      name: 'brightsky-store',
      partialize: (s) => ({
        accessToken: s.accessToken,
        refreshToken: s.refreshToken,
        userId: s.userId,
        userEmail: s.userEmail,
        userDisplayName: s.userDisplayName,
        authenticated: s.authenticated,
      }),
    }
  )
)
