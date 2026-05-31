import { useBrightskyStore, BRIGHTSKY_BASE_URL } from '../store/brightskyStore'
import { useChatStore } from '../store/chatStore'
import { collectPathlyContext } from './pathlyContextCollector'
import { executeStudioTool } from './studioAnalyzer'

export class BrightskyClient {
  private ws: WebSocket | null = null
  private streamInProgress = false
  private connectTimeout: ReturnType<typeof setTimeout> | null = null
  private streamContent = ''
  private intentionalDisconnect = false
  private wsUrl = ''
  private accessToken = ''
  private reconnectAttempts = 0
  private clientCapabilitiesSent = false

  connect(wsUrl: string, accessToken: string, resetReconnect = true): void {
    this.wsUrl = wsUrl
    this.accessToken = accessToken
    this.clientCapabilitiesSent = false
    if (resetReconnect) this.reconnectAttempts = 0

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

    const url = new URL(wsUrl)
    url.searchParams.set('token', accessToken)
    const ws = new WebSocket(url.toString())
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
        if (!this.clientCapabilitiesSent && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: 'client_capabilities',
            source: 'pathly-studio',
            capabilities: {
              canAnalyzeDom: false,
              canExecuteToolCalls: true,
              canStreamThinking: true,
              supportedToolTypes: ['studio_analyzer', 'automation'] as string[],
            },
            version: '1.0',
          }))
          this.clientCapabilitiesSent = true
        }
      } else if (type === 'typing_metadata') {
        const label = (data.label as string | undefined) ?? null
        useBrightskyStore.getState().setThinkingLabel(label)
      } else if (type === 'stream_chunk') {
        useBrightskyStore.getState().setThinkingLabel(null)
        const payload = data.payload as Record<string, unknown> | undefined
        const chunk = (payload?.chunk as string | undefined) ?? ''
        this.streamContent += chunk
        useChatStore.getState().updateLastMessage({ content: this.streamContent })
        if (payload?.isDone === true) {
          this.streamInProgress = false
          this.streamContent = ''
        }
      } else if (type === 'stream_end') {
        useBrightskyStore.getState().setThinkingLabel(null)
        this.streamInProgress = false
        this.streamContent = ''
      } else if (type === 'tool_call') {
        const callId = (data.callId as string | undefined) ?? ''
        const toolName = (data.toolName as string | undefined) ?? ''
        const parameters = data.parameters
        if (!callId || !toolName) return
        const socket = this.ws
        useBrightskyStore.getState().setToolCallInProgress(toolName)
        void (async () => {
          try {
            const result = await executeStudioTool(toolName, parameters)
            if (socket === this.ws && socket?.readyState === WebSocket.OPEN) {
              socket.send(JSON.stringify({
                type: 'tool_response',
                callId,
                payload: { result, success: true },
              }))
            }
          } catch (err) {
            if (socket === this.ws && socket?.readyState === WebSocket.OPEN) {
              socket.send(JSON.stringify({
                type: 'tool_response',
                callId,
                payload: { success: false, error: String(err instanceof Error ? err.message : err) },
              }))
            }
          } finally {
            useBrightskyStore.getState().setToolCallInProgress(null)
          }
        })()
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
      useBrightskyStore.getState().setThinkingLabel(null)
      useBrightskyStore.getState().setToolCallInProgress(null)
      if (!this.intentionalDisconnect) {
        const delays = [1000, 2000, 4000, 8000, 16000]
        const attempt = this.reconnectAttempts++
        if (attempt < delays.length) {
          setTimeout(() => {
            if (!this.intentionalDisconnect) this.connect(this.wsUrl, this.accessToken, false)
          }, delays[attempt])
        } else {
          useBrightskyStore.getState().setAuthError('Connection lost after 5 attempts — please sign in again.')
        }
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
      useBrightskyStore.getState().setThinkingLabel(null)
      useBrightskyStore.getState().setToolCallInProgress(null)
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
    useBrightskyStore.getState().setToolCallInProgress(null)
    const pathlyCtx = await collectPathlyContext()
    const sharedFields = {
      requestId: crypto.randomUUID(),
      messageType: 'pathly_chat',
      context: { source: 'pathly-studio', appContext: pathlyCtx.appContext },
      capabilities: {
        canAnalyzeDom: false,
        canExecuteToolCalls: true,
        canStreamThinking: true,
        supportedToolTypes: ['studio_analyzer', 'automation'] as string[],
      },
    }

    if (sessionId === null) {
      this.ws?.send(
        JSON.stringify({
          type: 'create_session_with_message',
          payload: { userMessage: { content, role: 'user' } },
          ...sharedFields,
        })
      )
    } else {
      this.ws?.send(JSON.stringify({
        type: 'user_message',
        content,
        sessionId,
        ...sharedFields,
      }))
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
