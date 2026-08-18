// What happens AFTER a spawned engine exits: tell the server what the run cost and produced.
//
// Two disjoint destinations, chosen by whether the tab was registered as a runner stage:
//   • runner stage  → POST /runner/terminal/result — the authoritative, run-keyed billing gate
//   • one-shot      → POST /db/invocation — project-tier telemetry for editor/HQ spawns
//
// Split out because this is reporting, not lifecycle: it runs once, at the end, and nothing in
// the spawn path depends on its outcome (both POSTs are best-effort with a single retry).

import { getApiSecret } from '@main/apiConfig'
import * as path from 'path'
import { parseClaudeJsonResult } from '../claudeJson'
import { parseCodexResult } from '../codexJson'
import { ptyOutput, runnerTabMeta, ptyKilledByRunner, sendToWindow } from './ptyRegistry'

/** Telemetry hint carried by renderer-driven one-shot spawns (editor AI actions, HQ summaries). */
export interface OneShotTelemetry {
  scopeTier: string
  label: string
  feature?: string
  role?: string
}

export function reportRunFinished(opts: {
  tabId: string
  exitCode: number
  cwd: string
  runnerArgv?: string[]
  telem?: OneShotTelemetry
  isOneShotTelem: boolean
  ptyStartedAt: number
  oneShotParsed: ReturnType<typeof parseClaudeJsonResult>
  toolUses: number
}): void {
  const { tabId, exitCode, cwd, runnerArgv, telem, isOneShotTelem, ptyStartedAt, oneShotParsed, toolUses } = opts
  const runnerMeta = runnerTabMeta.get(tabId)
  if (runnerMeta) {
    const userInitiated = ptyKilledByRunner.has(tabId)
    const stdoutTail = (ptyOutput.get(tabId) ?? []).join('')
    // Parse the claude --output-format=json result
    const stageResult = parseClaudeJsonResult(stdoutTail)
    if (stageResult) {
      sendToWindow(tabId, 'terminal:stage-result', tabId, stageResult)
    }
    const wallSeconds = (Date.now() - runnerMeta.spawnedAt) / 1000
    runnerTabMeta.delete(tabId)
    ptyOutput.delete(tabId)
    ptyKilledByRunner.delete(tabId)
    const label = runnerMeta.label || tabId
    const banner = exitCode === 0
      ? `\r\n\x1b[2m──\x1b[0m \x1b[1;32m${label} DONE\x1b[0m \x1b[2m──────────────────────────────\x1b[0m\r\n`
      : `\r\n\x1b[2m──\x1b[0m \x1b[1;31m${label} ABORTED\x1b[0m \x1b[2m──────────────────────────────\x1b[0m\r\n`
    sendToWindow(tabId, `terminal:data:${tabId}`, banner)
    // The adapter that SPAWNED this run (its launcher). Sent so the server parses the result
    // with the RIGHT usage parser instead of inferring from RunnerState.current_adapter,
    // which — under early-advance — may already point at the NEXT stage's engine, so a codex
    // stage's output would be parsed by the claude parser (no token usage) → 0 tokens / $0.
    const runnerAdapter = path.basename(runnerArgv?.[0] ?? '').toLowerCase().replace(/\.(ps1|cmd|exe)$/, '')
    const postBody = JSON.stringify({
      run_id: runnerMeta.run_id,
      topic: runnerMeta.topic,
      exit_code: exitCode,
      stdout_tail: stdoutTail,
      wall_seconds: wallSeconds,
      user_initiated: userInitiated,
      adapter: runnerAdapter,
    })
    const doPost = () => fetch('http://127.0.0.1:8765/runner/terminal/result', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Pathly-Secret': getApiSecret() },
      body: postBody,
    })
    doPost().catch(() => setTimeout(() => doPost().catch(() => { /* give up */ }), 1000))
  } else {
    // Renderer-driven one-shot (editor / chat): project its telemetry to the project tier
    // so EVERY CLI the app spawns is observable, not just supervisor-driven runs. Cost +
    // tokens come from the parsed JSON result (null for non-json/codex → span-only). Best-effort.
    if (isOneShotTelem && telem) {
      const wallSeconds = (Date.now() - ptyStartedAt) / 1000
      const engineBase = path.basename(runnerArgv?.[0] ?? '').toLowerCase().replace(/\.(ps1|cmd|exe)$/, '')
      // claude reports cost + tokens + result in one JSON envelope; codex emits JSONL with
      // tokens but NEVER a dollar cost, and parseClaudeJsonResult can't read it — so a codex
      // one-shot would be stuck at $0 / 0 tokens. Parse the codex stream here for tokens (the
      // server estimates cost from them via db/pricing.py) + the final agent message.
      const codex = !oneShotParsed && engineBase.includes('codex')
        ? parseCodexResult((ptyOutput.get(tabId) ?? []).join(''))
        : null
      const usage = oneShotParsed?.usage
      const invBody = JSON.stringify({
        project_root: cwd,
        feature: telem.feature ?? '(project)',
        scope_tier: telem.scopeTier || 'project',
        run_id: tabId,
        label: telem.label || 'one-shot',
        agent_role: telem.role || engineBase || 'agent',
        adapter: engineBase || 'claude',
        // The server re-parses stdout_tail with the ONE robust parser (parse_result) and
        // prefers it; these client-parsed values are a fallback (spawn-parse-unification).
        stdout_tail: (ptyOutput.get(tabId) ?? []).join(''),
        cost_usd: oneShotParsed?.total_cost_usd ?? 0,
        tokens_in: usage?.input_tokens ?? codex?.tokens_in ?? 0,
        tokens_out: usage?.output_tokens ?? codex?.tokens_out ?? 0,
        tool_uses: toolUses,
        session_id: null,
        summary: (oneShotParsed?.result ?? codex?.result ?? '').slice(0, 2000),
        wall_seconds: wallSeconds,
      })
      const postInv = () => fetch('http://127.0.0.1:8765/db/invocation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Pathly-Secret': getApiSecret() },
        body: invBody,
      })
      postInv().catch(() => setTimeout(() => postInv().catch(() => { /* give up */ }), 1000))
    }
    ptyOutput.delete(tabId)
  }
}
