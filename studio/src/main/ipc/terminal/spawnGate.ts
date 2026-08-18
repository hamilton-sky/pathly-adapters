// The CLI-engine spawn gate: how many engines may run at once, who waits, and what the
// monitor sees. Every spawn funnels through here.
//
// It also owns the transient-retry bookkeeping (`ptyKilledByUser` / `transientAttempts`),
// because a retry re-enters the gate — queue slot, caps, priority and cooldown all apply
// again — so the attempt counters belong to the gate, not to the PTY lifecycle.

import { BrowserWindow } from 'electron'
import { slog } from './log'

// Tabs the user explicitly stopped — suppresses the transient-failure retry, so Stop always
// means stop (ptyKilledByRunner only covers runner tabs, so it can't serve this).
export const ptyKilledByUser = new Set<string>()
// Maps tabId → how many times a transient provider failure has already been re-run.
export const transientAttempts = new Map<string, number>()

// ── CLI-engine spawn scheduler ───────────────────────────────────────────────
// One place controls how many CLI engines run at once. Every spawn funnels through
// terminal:spawn. Two classes of engine:
//   • headless one-shots (Analyze/Split/agents/board/goals) — capped and QUEUED.
//   • interactive sessions (chat / manual `claude`) — capped but REJECTED (never queued),
//     since they are long-lived and user-initiated.
// A global ceiling bounds the SUM so the machine/API are never flooded. All caps configurable.
const RATE_LIMIT_COOLDOWN_MS = 15000
export const CLI_ENGINES = new Set(['claude', 'codex', 'antigravity', 'agy', 'copilot'])

export const caps = { global: 8, headless: 5, interactive: 5 }
const gatedRunning = new Set<string>()        // headless one-shots currently running
export const interactiveRunning = new Set<string>()  // interactive engine sessions currently running
interface QueueItem { tabId: string; priority: number; resolve: () => void; reject: (e: Error) => void }
const engineQueue: QueueItem[] = []           // ordered — front runs next

// Identified live engines (PTY spawned, not yet exited) — the CLI monitor's SINGLE source of
// truth. Keyed by tabId; carries enough to render a monitor row WITHOUT the renderer's
// terminalStore (which a window reload would wipe while these PTYs keep running here). Populated
// right after pty.spawn; removed in releaseEngineSlot (the one place exit/kill/cancel converge).
export interface RunningEngine {
  tabId: string
  adapter: string
  label: string
  startedAt: number
  /** How the engine was spawned — the board's primary grouping (runner tab → flow, else single). */
  category: 'flow' | 'loop' | 'single'
  /** Feature/topic this engine serves, when known (runner topic or spawn telemetry.feature). */
  feature?: string
  /** Agent role from spawn telemetry (single-shot editor/AI actions); absent for runner tabs. */
  role?: string
  /** Pipeline run id (runner tabs only) — keys the per-flow cost rollup (/db/runs/<run_id>/cost). */
  runId?: string
  /** When the engine finished — set only on RECENT/history entries. */
  finishedAt?: number
}
export const activeEngines = new Map<string, RunningEngine>()
// Engines accepted by the gate but still WAITING for a slot (queued / paused). Same record shape,
// startedAt = when queued. Registered at request time so the monitor can render queued rows with a
// real adapter/category/feature, then moved to activeEngines when the PTY actually spawns.
export const queuedEngines = new Map<string, RunningEngine>()
// Recently-finished engines (bounded, newest first) — the monitor's RECENT/history list. Pushed in
// releaseEngineSlot (exit / kill / cancel) so a spawn's record is visible after it ends, and it
// survives a renderer reload (it lives in the main process).
const RECENT_CAP = 40
const recentEngines: RunningEngine[] = []



let queuePaused = false
let rateLimitedUntil = 0
let spawnStateWin: BrowserWindow | null = null

// `queuePaused` / `rateLimitedUntil` / `spawnStateWin` are module-private `let`s — a `let`
// cannot be exported and reassigned from another module, so the gate exposes intent-named
// mutators instead of raw bindings. That is a gain, not a workaround: callers now say what
// they mean ("arm the cooldown") rather than poking a counter.

/** Point the gate at the window that receives `spawn:state` pushes. */
export function setSpawnStateWindow(win: BrowserWindow): void {
  spawnStateWin = win
}

/** Pause/resume promotion of queued runs (queue-control UI). */
export function setQueuePaused(paused: boolean): void {
  queuePaused = paused
}

/** Back off the next gated runs after a provider refusal (rate limit / capacity / 5xx). */
export function armRateLimitCooldown(): void {
  rateLimitedUntil = Date.now() + RATE_LIMIT_COOLDOWN_MS
}

/** Milliseconds still to wait on the active rate-limit cooldown (0 when clear). */
export function rateLimitCooldownRemaining(): number {
  return Math.max(0, rateLimitedUntil - Date.now())
}

/** Live engines, for the renderer's synchronous liveness re-verify on mount. */
export function listActiveEngines(): RunningEngine[] {
  return Array.from(activeEngines.values())
}

/** Clear all gate state — process teardown only (see killAllPtys). */
export function resetGateState(): void {
  activeEngines.clear()
  queuedEngines.clear()
  ptyKilledByUser.clear()
  transientAttempts.clear()
}

export function spawnCounts(): string {
  return `running=${gatedRunning.size} interactive=${interactiveRunning.size} total=${totalRunning()}/${caps.global} queued=${engineQueue.length} paused=${queuePaused}`
}

export function totalRunning(): number { return gatedRunning.size + interactiveRunning.size }
export function canStartHeadless(): boolean {
  return !queuePaused && gatedRunning.size < caps.headless && totalRunning() < caps.global
}
export function canStartInteractive(): boolean {
  return interactiveRunning.size < caps.interactive && totalRunning() < caps.global
}

export function broadcastSpawnState(): void {
  try {
    spawnStateWin?.webContents.send('spawn:state', {
      running: gatedRunning.size,
      interactive: interactiveRunning.size,
      total: totalRunning(),
      engines: Array.from(activeEngines.values()),
      queuedEngines: Array.from(queuedEngines.values()),
      recentEngines: [...recentEngines],
      queued: engineQueue.map((w) => w.tabId),
      paused: queuePaused,
      rateLimitedUntil,
      caps: { ...caps },
    })
  } catch { /* ignore */ }
}

export function acquireEngineSlot(tabId: string, priority = 0, meta?: RunningEngine): Promise<void> {
  if (canStartHeadless()) {
    gatedRunning.add(tabId)
    broadcastSpawnState()
    return Promise.resolve()
  }
  if (meta) queuedEngines.set(tabId, meta)   // waiting for a slot → render it as a queued row
  return new Promise<void>((resolve, reject) => {
    const item: QueueItem = { tabId, priority, resolve, reject }
    // Keep priority items (runner/board) ahead of inline editor actions, preserving order in a tier.
    const idx = priority > 0 ? engineQueue.findIndex((w) => w.priority < priority) : -1
    if (idx === -1) engineQueue.push(item)
    else engineQueue.splice(idx, 0, item)
    broadcastSpawnState()
  })
}

// Start as many queued runs as the caps now allow (a freed interactive slot may unblock several).
export function promoteQueue(): void {
  while (engineQueue.length && canStartHeadless()) {
    const next = engineQueue.shift() as QueueItem
    gatedRunning.add(next.tabId)
    queuedEngines.delete(next.tabId)   // promoted to running — activeEngines.set follows after pty.spawn
    next.resolve()
  }
}

export function releaseEngineSlot(tabId: string): void {
  const finished = activeEngines.get(tabId) ?? queuedEngines.get(tabId)  // capture before delete → RECENT
  const wasEngine = activeEngines.delete(tabId)   // live engine gone (exit/kill) — drop from the monitor registry
  queuedEngines.delete(tabId)                     // also clear it if it was still waiting for a slot
  if (finished) {
    recentEngines.unshift({ ...finished, finishedAt: Date.now() })
    if (recentEngines.length > RECENT_CAP) recentEngines.length = RECENT_CAP
  }
  const qi = engineQueue.findIndex((w) => w.tabId === tabId)
  if (qi !== -1) {
    const [w] = engineQueue.splice(qi, 1) // cancelled while queued — reject so the spawn() call unblocks
    w.reject(new Error('cancelled'))
    // No onExit will fire for a spawn that never started, so clear the retry bookkeeping here.
    ptyKilledByUser.delete(tabId)
    transientAttempts.delete(tabId)
    slog('release: cancelled while queued', tabId, '|', spawnCounts())
    broadcastSpawnState()
    return
  }
  if (!gatedRunning.delete(tabId) && !interactiveRunning.delete(tabId)) {
    if (wasEngine) broadcastSpawnState()   // slot untracked but an engine was removed — keep the monitor honest
    slog('release: not tracked', tabId)
    return
  }
  slog('release', tabId, '|', spawnCounts())
  promoteQueue()
  broadcastSpawnState()
}

// Hold before starting a gated run if we recently hit a rate limit, so a 429 burst backs off.
export async function awaitRateLimitCooldown(): Promise<void> {
  const wait = rateLimitedUntil - Date.now()
  if (wait > 0) await new Promise<void>((r) => setTimeout(r, wait))
}

export function reorderQueue(tabId: string, dir: 'up' | 'down'): void {
  const i = engineQueue.findIndex((w) => w.tabId === tabId)
  if (i === -1) return
  const j = dir === 'up' ? i - 1 : i + 1
  if (j < 0 || j >= engineQueue.length) return
  const tmp = engineQueue[i]; engineQueue[i] = engineQueue[j]; engineQueue[j] = tmp
  broadcastSpawnState()
}
