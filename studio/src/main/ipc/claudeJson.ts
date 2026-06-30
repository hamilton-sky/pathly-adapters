// Pure parsing/rendering for claude CLI output — no Electron deps, so it is unit-testable.
//
//  - parseClaudeJsonResult: pull the final {"type":"result",…} object out of buffered
//    --output-format=json stdout (robust to the PTY wrapping it at the column width).
//  - feedStreamJson / handleStreamEvent: turn a claude --output-format=stream-json EVENT stream
//    back into clean terminal prose + "⚙ Tool" lines, while accumulating cost / tokens /
//    tool-call count. Used by the spawn gate (terminal.ts) so editor/chat one-shots keep live
//    streaming AND become observable.

export interface ClaudeJsonResult {
  result: string
  total_cost_usd: number
  duration_ms: number
  usage: {
    input_tokens: number
    output_tokens: number
    cache_read_input_tokens: number
    cache_creation_input_tokens: number
  }
  permission_denials?: Array<{
    tool_name: string
    tool_use_id?: string
    tool_input?: unknown
  }>
}

/** Extract the balanced { … } object starting at position 0.
 *  Handles string escaping so embedded braces inside strings are ignored. */
export function extractBalancedJson(s: string): string | null {
  let depth = 0
  let inString = false
  let escape = false
  for (let i = 0; i < s.length; i++) {
    const c = s[i]
    if (escape) { escape = false; continue }
    if (c === '\\' && inString) { escape = true; continue }
    if (c === '"') { inString = !inString; continue }
    if (inString) continue
    if (c === '{') depth++
    else if (c === '}') {
      depth--
      if (depth === 0) return s.slice(0, i + 1)
    }
  }
  return null
}

export function parseClaudeJsonResult(stdout: string): ClaudeJsonResult | null {
  // Strip ANSI escape sequences
  const stripped = stdout.replace(/\x1b\[[0-9;]*[mGKHFABCDJsu]/g, '')

  // Claude emits {"type":"result",...} as compact JSON on one logical line, but
  // the PTY terminal wraps it at the column width with \r\n sequences.  We find
  // the marker, walk back to the opening brace, flatten the PTY wrapping in
  // that section, then extract a balanced { } object before parsing.
  const idxA = stripped.lastIndexOf('"type":"result"')
  const idxB = stripped.lastIndexOf('"type": "result"')
  const markerIdx = Math.max(idxA, idxB)
  if (markerIdx === -1) return null

  // Walk backward to find the opening brace for this object
  let start = markerIdx
  while (start > 0 && stripped[start] !== '{') start--
  if (stripped[start] !== '{') return null

  // Flatten PTY-introduced \r\n wrapping within the JSON section only
  const flat = stripped.slice(start).replace(/\r\n/g, '').replace(/\r/g, '')
  const json = extractBalancedJson(flat)
  if (!json) return null

  try {
    const parsed = JSON.parse(json) as { type?: string } & ClaudeJsonResult
    if (parsed.type === 'result') return parsed
  } catch { /* malformed */ }
  return null
}

// ── stream-json renderer ─────────────────────────────────────────────────────

export interface StreamJsonState {
  buffer: string
  toolUses: number
  result: ClaudeJsonResult | null
  sawEvent: boolean
}

export function newStreamJsonState(): StreamJsonState {
  return { buffer: '', toolUses: 0, result: null, sawEvent: false }
}

type StreamEvent = {
  type?: string
  message?: { content?: Array<{ type?: string; text?: string; name?: string; input?: Record<string, unknown> }> }
} & Partial<ClaudeJsonResult>

/** Friendly one-line label for a tool_use event, e.g. "Edit(app.ts)" or "Bash(npm test)". */
export function streamToolLabel(block: { name?: string; input?: Record<string, unknown> }): string {
  const name = block.name ?? 'tool'
  const inp = block.input ?? {}
  const raw = String(inp.file_path ?? inp.path ?? inp.pattern ?? inp.command ?? inp.url ?? '')
  const base = raw.split(/[\\/]/).pop() ?? ''
  const short = base.length > 48 ? base.slice(0, 47) + '…' : base
  return short ? `${name}(${short})` : name
}

/** Render one parsed stream-json event to readable terminal text + capture telemetry. */
function handleStreamEvent(state: StreamJsonState, ev: StreamEvent, emit: (text: string) => void): void {
  if (ev.type === 'assistant' && Array.isArray(ev.message?.content)) {
    for (const block of ev.message.content) {
      if (block.type === 'text' && block.text) {
        emit(block.text.replace(/\r?\n/g, '\r\n') + '\r\n')
      } else if (block.type === 'tool_use') {
        state.toolUses++
        emit(`\x1b[2m⚙ ${streamToolLabel(block)}\x1b[0m\r\n`)
      }
    }
  } else if (ev.type === 'result') {
    state.result = ev as unknown as ClaudeJsonResult
  }
  // system/init + tool_result events are intentionally not rendered — keeps the terminal clean.
}

/** Feed raw PTY output for a stream-json one-shot: pull out complete JSON events (robust to the
 *  PTY inserting \r\n to wrap long lines and to non-JSON noise), render them via `emit`, and
 *  accumulate cost / tokens / tool-count. Never throws. */
export function feedStreamJson(state: StreamJsonState, chunk: string, emit: (text: string) => void): void {
  // Drop ANSI + ALL real CR/LF: those are BOTH the event separators AND the PTY's column-wrap.
  // Content newlines inside JSON strings are escaped as \\n (backslash+n), so they survive.
  state.buffer += chunk
    .replace(/\x1b\[[0-9;?]*[A-Za-z]/g, '')
    .replace(/\x1b\][\s\S]*?(?:\x07|\x1b\\)/g, '')
    .replace(/[\r\n]+/g, '')
  for (let guard = 0; guard < 1000; guard++) {
    const i = state.buffer.indexOf('{')
    if (i < 0) { state.buffer = ''; return }          // only noise so far — drop it
    if (i > 0) state.buffer = state.buffer.slice(i)   // discard leading non-JSON noise
    const obj = extractBalancedJson(state.buffer)
    if (!obj) {
      // No complete object yet. If an implausibly large run never balances, the leading '{' is a
      // stray inside noise — skip it so the parser can't wedge; otherwise wait for more data.
      if (state.buffer.length > 262_144) { state.buffer = state.buffer.slice(1); continue }
      return
    }
    let parsed: unknown
    try { parsed = JSON.parse(obj) } catch { parsed = null }
    if (parsed && typeof parsed === 'object') {
      state.sawEvent = true
      state.buffer = state.buffer.slice(obj.length)
      handleStreamEvent(state, parsed as StreamEvent, emit)
    } else {
      state.buffer = state.buffer.slice(1)            // stray '{' — advance past it
    }
  }
}
