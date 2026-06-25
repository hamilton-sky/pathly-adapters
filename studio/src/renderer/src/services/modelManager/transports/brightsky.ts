// Brightsky transport (one-shot).
//
// Brightsky is WS-streaming-only. The shared `brightskyClient` singleton
// (`lib/brightskyClient.ts`) is tightly coupled to the chat UI — its onmessage
// handler writes every `stream_chunk` straight into `useChatStore`. That is the
// wrong surface for a one-shot result, so here we open a short-lived WS using
// the SAME protocol and auth primitives the client uses
// (`create_session_with_message` / `user_message`, token from
// `useBrightskyStore`, `BRIGHTSKY_WS_URL`) and accumulate `stream_chunk`
// payloads until `stream_end`, resolving with the joined string.

import { useBrightskyStore, BRIGHTSKY_WS_URL } from '../../../store/brightskyStore'
import type { RunResult } from './types'

const CONNECT_TIMEOUT_MS = 90_000
const STREAM_TIMEOUT_MS = 120_000

/**
 * Run a single prompt against Brightsky and resolve with the full response text.
 * Requires the user to be authenticated (accessToken present in the store).
 */
export async function runBrightsky(prompt: string): Promise<RunResult> {
  const { accessToken, authenticated } = useBrightskyStore.getState()
  if (!authenticated || !accessToken) {
    throw new Error('Brightsky is not connected — please sign in first.')
  }

  return new Promise<RunResult>((resolve, reject) => {
    const url = new URL(BRIGHTSKY_WS_URL)
    url.searchParams.set('token', accessToken)
    const ws = new WebSocket(url.toString())

    let content = ''
    let settled = false
    let sessionId: string | null = null

    const connectTimer = setTimeout(() => fail(new Error('Brightsky connection timed out.')), CONNECT_TIMEOUT_MS)
    let streamTimer: ReturnType<typeof setTimeout> | null = null

    function cleanup(): void {
      clearTimeout(connectTimer)
      if (streamTimer) clearTimeout(streamTimer)
      try {
        ws.close()
      } catch {
        /* already closing */
      }
    }

    function succeed(): void {
      if (settled) return
      settled = true
      cleanup()
      resolve({ text: content })
    }

    function fail(err: Error): void {
      if (settled) return
      settled = true
      cleanup()
      reject(err)
    }

    function armStreamTimeout(): void {
      if (streamTimer) clearTimeout(streamTimer)
      streamTimer = setTimeout(() => fail(new Error('Brightsky stream timed out.')), STREAM_TIMEOUT_MS)
    }

    const sharedFields = {
      requestId: crypto.randomUUID(),
      messageType: 'pathly_chat',
      context: { source: 'pathly-studio' },
      capabilities: {
        canAnalyzeDom: false,
        canExecuteToolCalls: false,
        canStreamThinking: false,
        supportedToolTypes: [] as string[],
      },
    }

    ws.onopen = () => {
      clearTimeout(connectTimer)
      armStreamTimeout()
      ws.send(
        JSON.stringify({
          type: 'create_session_with_message',
          payload: { userMessage: { content: prompt, role: 'user' } },
          ...sharedFields,
        })
      )
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
        sessionId =
          (metadata?.sessionId as string | undefined) ?? (data.sessionId as string | undefined) ?? sessionId
      } else if (type === 'stream_chunk') {
        armStreamTimeout()
        const payload = data.payload as Record<string, unknown> | undefined
        content += (payload?.chunk as string | undefined) ?? ''
      } else if (type === 'stream_end') {
        succeed()
      }
    }

    ws.onerror = () => fail(new Error('Brightsky connection error.'))
    ws.onclose = () => {
      // If the socket closes after we've already accumulated content, treat it as
      // a (possibly truncated) success rather than a hard error.
      if (!settled) {
        if (content) succeed()
        else fail(new Error('Brightsky connection closed before any response.'))
      }
    }

    // sessionId is captured for protocol parity / future continuation; not used
    // beyond the single one-shot turn.
    void sessionId
  })
}
