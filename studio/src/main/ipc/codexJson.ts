// Pure parsing for codex `exec --json` JSONL output — no Electron deps, so it is unit-testable.
//
// Codex emits a stream of JSONL events on stdout and NEVER a dollar cost, and its shape is
// unlike claude's single {"type":"result",…} envelope — so parseClaudeJsonResult (claudeJson.ts)
// returns null for it and a codex one-shot would otherwise record $0 / 0 tokens. This scanner
// pulls the token usage (so the server can ESTIMATE cost via db/pricing.py) plus the final
// agent-message text (for the RECENT card summary).
//
// DEFENSIVE: codex's usage shape varies by CLI version. This mirrors the tolerated layouts in
// src/pathly_orchestrator/runner/output.py::_codex_usage — a top-level `usage` object, a nested
// `info.total_token_usage`, or a typed `token_count`/`token_usage` event whose own fields ARE the
// usage; snake_case and camelCase; keeps the LAST non-zero usage seen (later events carry the
// running/final total). Keep the two implementations in sync.

import { extractBalancedJson } from './claudeJson'

export interface CodexResult {
  result: string
  tokens_in: number
  tokens_out: number
}

function num(v: unknown): number {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : 0
}

type Obj = Record<string, unknown>
const isObj = (v: unknown): v is Obj => !!v && typeof v === 'object'

/** Extract the token usage from one parsed codex event, or null if it carries none. */
function usageFromEvent(obj: Obj): { in: number; out: number } | null {
  let usage: unknown = obj.usage
  if (!isObj(usage)) {
    const info = obj.info
    if (isObj(info) && isObj(info.total_token_usage)) usage = info.total_token_usage
    else if (obj.type === 'token_count' || obj.type === 'token_usage') usage = obj
  }
  if (!isObj(usage)) return null
  // `||` (not `??`) so a 0 falls through to the next alias — mirrors the Python `or` chain.
  const uin =
    (num(usage.input_tokens) || num(usage.prompt_tokens) || num(usage.inputTokens)) +
    (num(usage.cached_input_tokens) || num(usage.cache_read_input_tokens))
  // Reasoning tokens ARE billed as output (o-series / gpt-5 reasoning) — the real codex
  // `turn.completed` usage carries them as reasoning_output_tokens. Mirror the Python fix.
  const uout =
    (num(usage.output_tokens) || num(usage.completion_tokens) || num(usage.outputTokens)) +
    (num(usage.reasoning_output_tokens) || num(usage.reasoning_tokens))
  if (uin || uout) return { in: uin, out: uout }
  return null
}

/** Final agent-visible text of one event (used as the summary), or '' if none. */
function textFromEvent(obj: Obj): string {
  if (obj.type === 'agent_message' && typeof obj.text === 'string') return obj.text
  if ((obj.type === 'assistant' || obj.type === 'message') && typeof obj.text === 'string') return obj.text
  return ''
}

/** Parse buffered codex `exec --json` stdout. Returns null when no JSON events were seen at all
 *  (e.g. the process produced nothing) so callers can distinguish "codex, no output" from
 *  "codex, output but no usage". Never throws. */
export function parseCodexResult(stdout: string): CodexResult | null {
  // Drop ANSI, then ALL CR/LF: those are BOTH the JSONL separators AND the PTY's column-wrap.
  // Content newlines inside JSON strings are escaped as \\n, so they survive intact.
  let buf = stdout
    .replace(/\x1b\[[0-9;?]*[A-Za-z]/g, '')
    .replace(/\x1b\][\s\S]*?(?:\x07|\x1b\\)/g, '')
    .replace(/[\r\n]+/g, '')

  let tokensIn = 0
  let tokensOut = 0
  let result = ''
  let sawEvent = false

  for (let guard = 0; guard < 100_000; guard++) {
    const i = buf.indexOf('{')
    if (i < 0) break
    if (i > 0) buf = buf.slice(i)
    const objStr = extractBalancedJson(buf)
    if (!objStr) break
    buf = buf.slice(objStr.length)
    let parsed: unknown
    try {
      parsed = JSON.parse(objStr)
    } catch {
      buf = buf.slice(1) // stray '{' inside noise — advance past it
      continue
    }
    if (!isObj(parsed)) continue
    sawEvent = true
    const u = usageFromEvent(parsed)
    if (u) {
      tokensIn = u.in
      tokensOut = u.out
    } // keep LAST non-zero usage
    const t = textFromEvent(parsed)
    if (t) result = t
  }

  if (!sawEvent) return null
  return { result, tokens_in: tokensIn, tokens_out: tokensOut }
}
