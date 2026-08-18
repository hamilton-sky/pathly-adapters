// Terminal IPC — the spawn path and the handlers the renderer calls.
//
// This file orchestrates; it does not implement. The pieces it drives live in ./terminal/:
//   shells         — command/argv → (shell, args), launcher resolution, Windows temp script
//   spawnGate      — concurrency caps, queue, engine registry, retry bookkeeping
//   ptyRegistry    — the live per-tab maps + teardown
//   promptInjector — startup-gate answering and interactive prompt injection
//   spawnReporting — the post-exit telemetry / runner-result POSTs
//   preflight      — is this engine installed?

import { ipcMain, BrowserWindow, app, type IpcMainInvokeEvent } from 'electron'
import * as fs from 'fs'
import * as path from 'path'
import { parseClaudeJsonResult, feedStreamJson, newStreamJsonState, type StreamJsonState } from './claudeJson'
import { classifyEngineFailure, MAX_TRANSIENT_RETRIES, retryDelayMs } from './engineFailure'
import { slog } from './terminal/log'
import {
  ALLOWED_SHELLS, RESOLVABLE_ENGINES, ENGINE_INSTALL_HINTS, adapterIdFromLauncher, isValidCwd,
  enrichedPath, resolveEngineLauncher, resolveShell, resolveInteractiveShell, resolveRunnerShell,
} from './terminal/shells'
import { preflightEngines } from './terminal/preflight'
import {
  activePtys, ptyWindows, ptyOwners, ptyOutput, runnerTabMeta, ptyKilledByRunner, runnerScripts,
  sendToWindow, tailMeaningfulOutput, killPtyTree,
} from './terminal/ptyRegistry'
import { attachStartupHandling } from './terminal/promptInjector'
import { reportRunFinished, type OneShotTelemetry } from './terminal/spawnReporting'
import { openTerminalPopout } from './terminal/popout'
import {
  CLI_ENGINES, caps, interactiveRunning, activeEngines, queuedEngines, type RunningEngine,
  acquireEngineSlot, releaseEngineSlot, awaitRateLimitCooldown, broadcastSpawnState,
  canStartHeadless, canStartInteractive, promoteQueue, reorderQueue, spawnCounts, totalRunning,
  ptyKilledByUser, transientAttempts, rateLimitCooldownRemaining,
  setSpawnStateWindow, setQueuePaused, armRateLimitCooldown, listActiveEngines,
} from './terminal/spawnGate'

// Re-exported so main/index.ts keeps its single import site for terminal teardown.
export { killAllPtys } from './terminal/ptyRegistry'

let pty: typeof import('node-pty') | null = null
try {
  pty = require('node-pty')
} catch {
  console.warn('[terminal] node-pty not available')
}

/** Telemetry hint passed by renderer-driven one-shot spawns (editor AI actions, HQ
 *  summaries) so the spawn gate can project a project-tier invocation+span for them.
 *  Absent for runner/board tabs — those are projected Python-side by the supervisor. */
interface SpawnTelemetryMeta { telemetry?: OneShotTelemetry }

export function registerTerminalHandlers(win: BrowserWindow): void {
  setSpawnStateWindow(win)
  // The spawn path is a named function (not just an inline handler) so a transient provider
  // failure can re-enter it — a retry then goes back through the SAME gate: queue slot, caps,
  // priority and rate-limit cooldown all apply again, instead of bypassing them.
  async function handleSpawn(event: IpcMainInvokeEvent, tabId: string, cwd: string, command?: string, runnerArgv?: string[], initialInput?: string, spawnMeta?: SpawnTelemetryMeta): Promise<void> {
    slog('request', tabId, '| command=' + (command ?? '-'), 'argv0=' + (runnerArgv?.[0] ?? '-'), 'hasInput=' + !!initialInput, '|', spawnCounts())
    if (!pty) { console.error('[spawn] reject: node-pty unavailable', tabId); throw new Error('node-pty is not available') }
    if (activePtys.has(tabId)) {
      console.error('[spawn] reject: tab already exists', tabId)
      throw new Error('Tab already exists')
    }

    if (!cwd) {
      throw new Error('Working directory is required')
    }

    if (!isValidCwd(cwd)) {
      throw new Error('Invalid working directory: ' + cwd)
    }

    let shell: string
    let shellArgs: string[]
    let tempScript: string | undefined

    if (runnerArgv && runnerArgv.length > 0) {
      if (!ALLOWED_SHELLS.has(runnerArgv[0])) {
        throw new Error('Shell not allowed: ' + runnerArgv[0])
      }
      // Resolve the engine to an absolute launcher so a self-update that rewrites the PATH
      // shim doesn't kill this stage with CommandNotFound. Gating below still keys off the
      // original bare name, so queue classification is unchanged.
      let effectiveArgv = runnerArgv
      if (RESOLVABLE_ENGINES.has(runnerArgv[0])) {
        const launcher = await resolveEngineLauncher(runnerArgv[0])
        if (launcher !== runnerArgv[0]) {
          effectiveArgv = [launcher, ...runnerArgv.slice(1)]
          slog('resolved engine', runnerArgv[0], '→', launcher)
        }
      }
      if (initialInput) {
        // Interactive runner: open the CLI normally so the user can keep chatting after
        ;({ shell, args: shellArgs } = resolveInteractiveShell(effectiveArgv))
      } else {
        // Headless runner: PTY exits when agent finishes
        ;({ shell, args: shellArgs, tempScript } = resolveRunnerShell(effectiveArgv))
      }
      if (tempScript) runnerScripts.set(tabId, tempScript)
    } else {
      // Manual terminal tab: just the adapter name
      if (command !== undefined && !ALLOWED_SHELLS.has(command)) {
        throw new Error('Shell not allowed: ' + command)
      }
      ;({ shell, args: shellArgs } = resolveShell(command))
    }

    // The monitor record for this engine, from what's known now: adapter, plus category/feature/
    // role from the runner topic or spawn telemetry. Used both while queued (waiting for a slot)
    // and once the PTY spawns, so a queued engine renders with the same identity it'll run with.
    const buildEngineMeta = (startedAt: number): RunningEngine => {
      const rmeta = runnerTabMeta.get(tabId)
      const adapter = adapterIdFromLauncher(runnerArgv?.[0] ?? command ?? '')
      return {
        tabId,
        adapter,
        label: rmeta?.label ?? spawnMeta?.telemetry?.label ?? adapter,
        startedAt,
        // Prefer the explicit category from the spawn payload (board one-shot → 'single',
        // FSM pipeline → 'flow'); fall back to the old presence-based guess for any spawn
        // that predates the threaded category. Fixes board single-agent runs reading as FLOW.
        category: rmeta?.category ?? (rmeta ? 'flow' : 'single'),
        feature: rmeta?.topic ?? spawnMeta?.telemetry?.feature,
        role: spawnMeta?.telemetry?.role,
        runId: rmeta?.run_id,
      }
    }

    // Gate only headless CLI-engine runs (not interactive sessions or manual shells). The slot
    // is held until the PTY exits (released in onExit/kill), so the cap limits RUNNING engines.
    const argvEngine = !!runnerArgv && runnerArgv.length > 0 && CLI_ENGINES.has(runnerArgv[0])
    const cmdEngine = !!command && CLI_ENGINES.has(command)
    const headlessEngine = argvEngine && !initialInput            // one-shot — queued
    const interactiveEngine = (argvEngine && !!initialInput) || cmdEngine  // chat / manual — rejected over cap
    if (headlessEngine) {
      // Runner/board stages register before spawn → give them priority so a headless burst
      // can't starve the pipeline. Then honor any active rate-limit cooldown.
      const priority = runnerTabMeta.has(tabId) ? 10 : 0
      slog('headless', tabId, canStartHeadless() ? 'run now' : 'QUEUED', 'priority=' + priority, '|', spawnCounts())
      await acquireEngineSlot(tabId, priority, buildEngineMeta(Date.now()))
      const cd = rateLimitCooldownRemaining()
      if (cd > 0) slog('headless', tabId, `rate-limit cooldown ${cd}ms`)
      await awaitRateLimitCooldown()
    } else if (interactiveEngine) {
      if (!canStartInteractive()) {
        console.error('[spawn] reject: interactive over cap', tabId, '|', spawnCounts())
        throw new Error(`Too many engines running (${totalRunning()}/${caps.global}). Close a session before opening another.`)
      }
      interactiveRunning.add(tabId)
      slog('interactive', tabId, 'run now', '|', spawnCounts())
      broadcastSpawnState()
    } else {
      slog('ungated', tabId, '(manual shell / non-engine)')
    }

    let ptyProcess: import('node-pty').IPty
    try {
      ptyProcess = pty.spawn(shell, shellArgs, {
        name: 'xterm-color',
        cols: 80,
        rows: 24,
        cwd: cwd,
        // Export PATHLY_PROJECT_ROOT so the stop hook (which runs as a child of this
        // agent PTY) can find the active feature in the DB and write the BILLING_UPDATE.
        // Without it, stop_telemetry.py hits `if not project_root: sys.exit(0)` and
        // in-app COST silently stays blank. cwd IS the project root (validated above);
        // the hook forward-slash-normalizes it, matching the stored fsm_events key.
        // Runner spawns are billed authoritatively by the gate → /runner/terminal/result
        // (adapter-agnostic, run-keyed). Mark them so the claude stop hook SKIPS them and can't
        // double-bill / mis-attribute via its "most recent feature" guess. Interactive claude
        // (no runner tab) carries no marker, so the hook still bills it (its only cost source).
        env: {
          ...process.env,
          // Widened PATH — a Finder-launched Electron app inherits launchd's minimal PATH,
          // not the user's shell PATH, so without this an engine (or a tool the engine
          // shells out to) can be unresolvable even though it works in the user's terminal.
          PATH: enrichedPath(),
          PATHLY_PROJECT_ROOT: cwd,
          ...(runnerTabMeta.has(tabId) ? { PATHLY_GATE_BILLED: '1' } : {}),
        } as Record<string, string>,
      })
    } catch (e) {
      console.error('[spawn] pty.spawn FAILED', tabId, 'shell=' + shell, 'args=' + JSON.stringify(shellArgs).slice(0, 200), '→', (e as Error).message)
      if (headlessEngine || interactiveEngine) releaseEngineSlot(tabId)
      // A missing engine binary is by far the most common spawn failure, and a bare
      // ENOENT tells the user nothing. Name the engine and the command that installs it.
      const wanted = runnerArgv?.[0] ?? command
      const bare = wanted ? path.basename(wanted).replace(/\.(ps1|cmd|exe)$/, '') : ''
      if (RESOLVABLE_ENGINES.has(bare) && /ENOENT|not found|cannot find/i.test((e as Error).message)) {
        throw new Error(
          `'${bare}' is not installed, or is not visible to Pathly. ` +
          `Install it with: ${ENGINE_INSTALL_HINTS[bare] ?? `install ${bare}`}`,
        )
      }
      throw e
    }
    const ptyStartedAt = Date.now()

    // Register this live engine with the authoritative gate so the CLI monitor renders EVERY
    // running engine — board/runner, editor one-shot, and manual REPL — from ONE source of truth,
    // not the renderer's per-tab status (which races the spawn round-trip and misses backend runs).
    if (headlessEngine || interactiveEngine) {
      activeEngines.set(tabId, buildEngineMeta(ptyStartedAt))
      queuedEngines.delete(tabId)   // was queued (if at all) → now running
      broadcastSpawnState()
    }

    // Default target window is the main window
    ptyWindows.set(tabId, win)
    // Phase 2: record ownership
    ptyOwners.set(tabId, event.sender.id)

    attachStartupHandling(ptyProcess, { tabId, initialInput, headlessEngine })

    // Stream-json one-shots (editor / chat) asked claude for an event stream so the gate can
    // capture cost/tokens/tool-calls. Render those events to clean prose + "⚙ Tool" lines instead
    // of dumping raw JSON. ONLY these tabs are affected — every other spawn is byte-identical.
    const isStreamJsonTab = headlessEngine && !runnerTabMeta.has(tabId)
      && !!spawnMeta?.telemetry && !!runnerArgv?.includes('stream-json')
    const streamState: StreamJsonState | null = isStreamJsonTab ? newStreamJsonState() : null

    ptyProcess.onData((data: string) => {
      if (streamState) {
        feedStreamJson(streamState, data, (text) => sendToWindow(tabId, `terminal:data:${tabId}`, text))
      } else {
        sendToWindow(tabId, `terminal:data:${tabId}`, data)
      }
      // Buffer a rolling RAW tail for every tab so onExit can report the real failure reason for
      // notebook/editor AI actions too (stream tabs read the clean result from streamState).
      const lines = ptyOutput.get(tabId) ?? []
      lines.push(data)
      if (lines.length > 500) lines.splice(0, lines.length - 500)
      ptyOutput.set(tabId, lines)
    })

    ptyProcess.onExit(({ exitCode }) => {
      const wallS = ((Date.now() - ptyStartedAt) / 1000).toFixed(1)
      const isEngine = headlessEngine || interactiveEngine
      const dbgTail = tailMeaningfulOutput(ptyOutput.get(tabId) ?? []).slice(-500).replace(/\s+/g, ' ').trim()
      if (exitCode !== 0) console.error('[spawn] exit', tabId, 'code=' + exitCode, `(${wallS}s)`, '| tail:', dbgTail || '(no output)')
      else if (isEngine) slog('exit', tabId, 'code=0', `(${wallS}s) engine | tail:`, dbgTail || '(no output)')
      else slog('exit', tabId, 'code=0', `(${wallS}s)`)
      activePtys.delete(tabId)
      ptyOwners.delete(tabId)
      releaseEngineSlot(tabId)
      const scriptPath = runnerScripts.get(tabId)
      if (scriptPath) { runnerScripts.delete(tabId); try { fs.unlinkSync(scriptPath) } catch { /* ignore */ } }
      const exitTailRaw = tailMeaningfulOutput(ptyOutput.get(tabId) ?? [])
      // One-shot telemetry: a gated headless engine run that is NOT a runner tab but carries a
      // telemetry hint (editor AI actions, HQ summaries). Cost/tokens/tool-count come from the
      // stream-json renderer's captured result event; the exit tail is normalized to the agent's
      // result prose so stdout-reading consumers (aiRouter) stay clean instead of seeing JSON.
      const telem = spawnMeta?.telemetry
      const isOneShotTelem = headlessEngine && !runnerTabMeta.has(tabId) && !!telem
      const oneShotParsed = streamState?.result
        ?? (isOneShotTelem ? parseClaudeJsonResult((ptyOutput.get(tabId) ?? []).join('')) : null)
      const exitTail = oneShotParsed?.result ? oneShotParsed.result.slice(-4000) : exitTailRaw
      // Did the PROVIDER refuse this turn (rate limit / quota / at capacity / 5xx), as opposed to
      // the agent failing on its own? Only that class is worth backing off and re-running.
      const transient = classifyEngineFailure(exitCode, exitTailRaw) === 'transient'

      // Transient retry. A gated headless run that the provider refused produced nothing, so
      // re-running it is safe in the way a normal failure is not — and without this the caller
      // (editor one-shot, runner stage) just reports "no file produced" for a fault that had
      // nothing to do with the prompt. Bounded, backed off, and never applied to a run the user
      // stopped. Returns BEFORE terminal:exit / the telemetry+runner POSTs fire, so consumers
      // see one exit for the whole attempt chain, not one per attempt.
      const attempts = transientAttempts.get(tabId) ?? 0
      if (transient && headlessEngine && !ptyKilledByUser.has(tabId) && attempts < MAX_TRANSIENT_RETRIES) {
        const attempt = attempts + 1
        transientAttempts.set(tabId, attempt)
        armRateLimitCooldown()
        broadcastSpawnState()
        const delay = retryDelayMs(attempt)
        console.error('[spawn] transient failure', tabId, `— retry ${attempt}/${MAX_TRANSIENT_RETRIES} in ${delay}ms |`, exitTailRaw.slice(-200).replace(/\s+/g, ' ').trim())
        sendToWindow(tabId, `terminal:data:${tabId}`, `\r\n\x1b[2m──\x1b[0m \x1b[1;33mengine unavailable — retrying (${attempt}/${MAX_TRANSIENT_RETRIES}) in ${Math.round(delay / 1000)}s\x1b[0m\r\n`)
        ptyOutput.delete(tabId)   // the next attempt must be judged on its OWN output, not this one's
        setTimeout(() => {
          if (ptyKilledByUser.has(tabId)) {   // stopped while we were backing off
            ptyKilledByUser.delete(tabId)
            transientAttempts.delete(tabId)
            return
          }
          void handleSpawn(event, tabId, cwd, command, runnerArgv, initialInput, spawnMeta).catch((e) => {
            // The retry never started (queue cancelled, engine vanished). Report the ORIGINAL
            // failure rather than stranding the tab with no exit event at all.
            console.error('[spawn] transient retry failed to start', tabId, '→', (e as Error).message)
            transientAttempts.delete(tabId)
            sendToWindow(tabId, 'terminal:exit', tabId, exitCode, exitTail)
          })
        }, delay)
        return
      }
      transientAttempts.delete(tabId)
      ptyKilledByUser.delete(tabId)

      // If a gated engine run hit a rate limit, arm a cooldown so the next gated runs back off.
      if (headlessEngine && transient) {
        armRateLimitCooldown()
        broadcastSpawnState()
      }
      sendToWindow(tabId, 'terminal:exit', tabId, exitCode, exitTail)
      reportRunFinished({
        tabId, exitCode, cwd, runnerArgv, telem, isOneShotTelem, ptyStartedAt, oneShotParsed,
        toolUses: streamState?.toolUses ?? 0,
      })
      ptyWindows.delete(tabId)
    })

    activePtys.set(tabId, ptyProcess)
  }

  ipcMain.handle('terminal:spawn', (event, tabId: string, cwd: string, command?: string, runnerArgv?: string[], initialInput?: string, spawnMeta?: SpawnTelemetryMeta) =>
    handleSpawn(event, tabId, cwd, command, runnerArgv, initialInput, spawnMeta))

  ipcMain.on('terminal:write', (event, tabId: string, data: string) => {
    // Phase 2: only allow the owning sender to write
    if (ptyOwners.get(tabId) !== event.sender.id) return
    const MAX_WRITE = 65536 // 64KB
    if (typeof data !== 'string' || data.length > MAX_WRITE) return
    activePtys.get(tabId)?.write(data)
  })

  ipcMain.handle('terminal:resize', (event, tabId: string, cols: number, rows: number) => {
    if (ptyOwners.get(tabId) !== event.sender.id) return
    const safeCols = Math.max(1, Math.min(500, Math.floor(Number(cols))))
    const safeRows = Math.max(1, Math.min(500, Math.floor(Number(rows))))
    activePtys.get(tabId)?.resize(safeCols, safeRows)
  })

  ipcMain.handle('terminal:kill', (event, tabId: string) => {
    const p = activePtys.get(tabId)
    if (p) {
      // A live PTY exists — enforce ownership before force-killing it.
      if (ptyOwners.get(tabId) !== event.sender.id) return
      ptyKilledByUser.add(tabId)   // suppress any transient retry — Stop means stop
      if (runnerTabMeta.has(tabId)) {
        ptyKilledByRunner.add(tabId)
      }
      killPtyTree(p)
      activePtys.delete(tabId)
      ptyOwners.delete(tabId)
      ptyWindows.delete(tabId)
      releaseEngineSlot(tabId)
      return
    }
    // No PTY yet — the spawn is still queued (the UI shows it as optimistically running), or it
    // is backing off between transient retries. Both windows must be stoppable, and neither
    // carries a ptyOwners entry to check. Mirrors the unguarded queue-control 'cancel' path.
    ptyKilledByUser.add(tabId)
    releaseEngineSlot(tabId)
  })

  ipcMain.handle('terminal:queue-control', (_event, action: {
    type: 'pause' | 'resume' | 'cancel' | 'reorder' | 'set-caps'
    tabId?: string
    dir?: 'up' | 'down'
    caps?: Partial<{ global: number; headless: number; interactive: number }>
  }) => {
    switch (action.type) {
      case 'pause': setQueuePaused(true); broadcastSpawnState(); break
      case 'resume': setQueuePaused(false); promoteQueue(); broadcastSpawnState(); break
      case 'cancel': if (action.tabId) releaseEngineSlot(action.tabId); break // rejects the queued spawn
      case 'reorder': if (action.tabId && action.dir) reorderQueue(action.tabId, action.dir); break
      case 'set-caps':
        if (action.caps) {
          if (typeof action.caps.global === 'number') caps.global = Math.max(1, Math.min(32, Math.floor(action.caps.global)))
          if (typeof action.caps.headless === 'number') caps.headless = Math.max(1, Math.min(32, Math.floor(action.caps.headless)))
          if (typeof action.caps.interactive === 'number') caps.interactive = Math.max(1, Math.min(32, Math.floor(action.caps.interactive))) // min 1 — a 0 cap rejects every interactive spawn
          promoteQueue() // raising caps may unblock queued runs
          broadcastSpawnState()
        }
        break
    }
  })

  ipcMain.handle('terminal:preflight', async (_event, force?: boolean) => preflightEngines(force === true))

  // Synchronous snapshot of the LIVE gate engines (main-process-owned, so it survives a
  // renderer reload). Lets a renderer that reloaded mid-run re-verify a one-shot's liveness
  // authoritatively on mount — unlike the async `spawn:state` push, which can arrive empty
  // first and race a reconcile into false-clearing a run that is actually still alive.
  ipcMain.handle('terminal:get-engines', () => listActiveEngines())

  ipcMain.handle('terminal:register-runner', (_event, tabId: string, topic: string, runId: string, label?: string, category?: 'flow' | 'loop' | 'single') => {
    runnerTabMeta.set(tabId, { run_id: runId, topic, spawnedAt: Date.now(), label: label ?? tabId, category })
  })

  ipcMain.handle('terminal:popout', (event, tabId: string, label: string) =>
    openTerminalPopout(event, tabId, label))
}
