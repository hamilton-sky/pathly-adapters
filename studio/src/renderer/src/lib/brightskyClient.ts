import { useBrightskyStore, BRIGHTSKY_BASE_URL } from '../store/brightskyStore'
import { useChatStore } from '../store/chatStore'

export class BrightskyClient {
  private ws: WebSocket | null = null
  private streamInProgress = false
  private connectTimeout: ReturnType<typeof setTimeout> | null = null
  private streamContent = ''
  private intentionalDisconnect = false

  connect(wsUrl: string, accessToken: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return

    if (this.connectTimeout) {
      clearTimeout(this.connectTimeout)
      this.connectTimeout = null
    }

    this.connectTimeout = setTimeout(() => {
      this.connectTimeout = null
      useBrightskyStore.getState().setConnected(false)
      useBrightskyStore.getState().setAuthError(
        'Connection timed out — the backend may be starting up. Try again in a moment.'
      )
    }, 90000)

    const ws = new WebSocket(wsUrl)
    this.ws = ws

    ws.onopen = () => {
      if (this.connectTimeout) {
        clearTimeout(this.connectTimeout)
        this.connectTimeout = null
      }
      useBrightskyStore.getState().setConnected(true)
    }

    ws.onmessage = (e: MessageEvent) => {
      let data: Record<string, unknown>
      try {
        data = JSON.parse(e.data as string) as Record<string, unknown>
      } catch {
        return
      }

      const type = data.type as string | undefined

      if (type === 'session_created') {
        const metadata = data.metadata as Record<string, unknown> | undefined
        const sessionId =
          (metadata?.sessionId as string | undefined) ??
          (data.sessionId as string | undefined) ??
          null
        if (sessionId) useBrightskyStore.getState().setSessionId(sessionId)
      } else if (type === 'stream_chunk') {
        const payload = data.payload as Record<string, unknown> | undefined
        const chunk = (payload?.chunk as string | undefined) ?? ''
        this.streamContent += chunk
        useChatStore.getState().updateLastMessage({ content: this.streamContent })
        if (payload?.isDone === true) {
          this.streamInProgress = false
          this.streamContent = ''
        }
      } else if (type === 'stream_end') {
        this.streamInProgress = false
        this.streamContent = ''
      } else if (type === 'processing_status') {
        // no dedicated status field in brightskyStore — intentionally ignored
      }
    }

    ws.onclose = () => {
      useBrightskyStore.getState().setConnected(false)
      if (this.streamInProgress) {
        const current = useChatStore.getState().messages
        const last = current[current.length - 1]
        const prev = (last?.content as string | undefined) ?? ''
        useChatStore.getState().updateLastMessage({
          content: prev + '\n\n_(incomplete — connection lost)_',
        })
      }
      this.streamInProgress = false
      this.streamContent = ''
      if (!this.intentionalDisconnect) {
        useBrightskyStore.getState().setAuthError('Disconnected from Brightsky.')
      }
      this.intentionalDisconnect = false
      this.ws = null
    }

    ws.onerror = () => {
      useBrightskyStore.getState().setConnected(false)
      if (this.streamInProgress) {
        const current = useChatStore.getState().messages
        const last = current[current.length - 1]
        const prev = (last?.content as string | undefined) ?? ''
        useChatStore.getState().updateLastMessage({
          content: prev + '\n\n_(incomplete — connection lost)_',
        })
      }
      this.streamInProgress = false
      this.streamContent = ''
      useBrightskyStore.getState().setAuthError('Disconnected from Brightsky.')
    }
  }

  async sendMessage(content: string, sessionId: string | null): Promise<void> {
    await this.maybeRefreshToken()

    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      useBrightskyStore.getState().setAuthError('Not connected — please wait for the connection to open.')
      return
    }

    useChatStore.getState().addMessage({
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      status: 'streaming',
    })
    this.streamContent = ''
    this.streamInProgress = true

    if (sessionId === null) {
      this.ws?.send(
        JSON.stringify({
          type: 'create_session_with_message',
          payload: { userMessage: { content, role: 'user' } },
        })
      )
    } else {
      this.ws?.send(JSON.stringify({ type: 'user_message', content, sessionId }))
    }
  }

  stopGeneration(sessionId: string): void {
    this.ws?.send(JSON.stringify({ type: 'stop_generation', sessionId }))
    this.streamInProgress = false
    this.streamContent = ''
  }

  disconnect(): void {
    if (this.connectTimeout) {
      clearTimeout(this.connectTimeout)
      this.connectTimeout = null
    }
    if (this.ws) {
      this.intentionalDisconnect = true
      this.ws.close()
    }
    useBrightskyStore.getState().setConnected(false)
  }

  private async maybeRefreshToken(): Promise<void> {
    const { accessToken, refreshToken } = useBrightskyStore.getState()
    if (!accessToken) return

    let exp: number
    try {
      const payload = JSON.parse(atob(accessToken.split('.')[1])) as { exp: number }
      exp = payload.exp
    } catch {
      return
    }

    if (exp - Date.now() / 1000 >= 60) return

    try {
      const res = await fetch(`${BRIGHTSKY_BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      if (!res.ok) throw new Error(`Refresh failed: ${res.status}`)
      const data = (await res.json()) as {
        access_token: string
        refresh_token: string
        user: { id: string; email: string; displayName: string }
      }
      useBrightskyStore.getState().setTokens(data.access_token, data.refresh_token, data.user)
    } catch (err) {
      useBrightskyStore.getState().clearAuth()
      throw err
    }
  }
}

export const brightskyClient = new BrightskyClient()
