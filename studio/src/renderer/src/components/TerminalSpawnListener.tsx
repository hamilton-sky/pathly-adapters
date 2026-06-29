import { useEffect } from 'react'
import { useRunnerStore } from '../store/runnerStore'
import { useProjectStore } from '../store/projectStore'
import { useTerminalStore } from '../store/terminalStore'
import { useToastStore } from '../store/toastStore'
import { attachProgress } from './shared/RunPill/progress'
import type { TerminalTab } from '../types/terminal'
import { apiFetch } from '../lib/config'
import * as xtermRegistry from './Terminal/xtermRegistry'

/**
 * App-level terminal lifecycle listener — the ONE place that opens and kills PTYs.
 *
 * Subscribes to /events/spawn for the app's lifetime, independent of which panel
 * is shown or whether the chat is open. Renders nothing.
 *
 * This previously lived inside useHQ (the chat hook), which is only mounted when
 * the chat panel is open. That meant a board run started from the CommandCenter
 * with the chat closed had no listener — TERMINAL_SPAWN was dropped and the
 * terminal never opened. Mounting this at app level fixes that: the spawn channel
 * is topic-independent AND view-independent.
 */
export function TerminalSpawnListener(): null {
  useEffect(() => {
    let es: EventSource | null = null
    let retry = 0
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null

    // Unified per-spawn progress: every headless board/runner agent gets the SAME start →
    // per-line → done toasts the Markdown Editor already shows (via the shared attachProgress),
    // instead of a separate ad-hoc mechanism. Keyed by tab so onExit can finish + clean up.
    const progressByTab = new Map<string, { stop: () => void; label: string }>()
    const exitUnsub = window.pathly.terminal.onExit((tabId: string, exitCode?: number) => {
      const entry = progressByTab.get(tabId)
      if (!entry) return
      entry.stop()
      progressByTab.delete(tabId)
      const ok = !exitCode
      useToastStore.getState().push(
        ok ? `Agent done · ${entry.label}` : `Agent failed · ${entry.label} (exit ${exitCode})`,
        ok ? 'success' : 'error',
        { category: 'agent_done' },
      )
    })

    const openTerminal = (data: Record<string, unknown>): void => {
      const tab_id = data.tab_id as string
      const run_id = data.run_id as string
      const topic = (data.topic as string | undefined) ?? ''   // from the event, NOT the active UI
      const adapter = data.adapter as string
      const label = (data.label as string | undefined) ?? adapter
      // Use || (not ??) so an empty-string cwd falls back to the project root — an
      // empty cwd makes node-pty fail silently and the run times out. runnerStore.projectRoot
      // is only set during an FSM pipeline run, so for board/goal runs fall back to the
      // canonical selected project (projectStore) before giving up.
      const cwd =
        (data.cwd as string | undefined) ||
        useRunnerStore.getState().projectRoot ||
        useProjectStore.getState().projectPath ||
        ''
      const prompt = (data.prompt as string | undefined) ?? ''
      const isInteractive = !!(data.interactive as boolean | undefined)
      if (useTerminalStore.getState().tabs.some((t) => t.id === tab_id)) return   // idempotent — never double-open
      if (!cwd) console.warn('[spawn] no working directory for', tab_id, '— PTY may fail to start')
      useTerminalStore.getState().addTab(tab_id, label, 'left', adapter as TerminalTab['kind'], undefined, undefined, prompt)
      useTerminalStore.getState().openTab(tab_id)
      // Unified progress toasts for HEADLESS board/runner agents (the silent ones) — the same
      // attachProgress the Markdown Editor uses: start now, per-line milestones while it runs,
      // and a done/failed toast on exit (handled by onExit above). Interactive REPLs are visible,
      // so skip them.
      if (!isInteractive) {
        useToastStore.getState().push(`Agent started · ${label}`, 'info', { category: 'phase_summary' })
        const stopProgress = attachProgress(tab_id, () => {}, (line) =>
          useToastStore.getState().push(`${label}: ${line}`, 'info', { category: 'phase_summary' }))
        progressByTab.set(tab_id, { stop: stopProgress, label })
      }
      useTerminalStore.setState((st) => ({
        tabs: st.tabs.map((t) => t.id === tab_id ? { ...t, runnerOwned: true } : t),
      }))
      useRunnerStore.getState().attachTerminalToStage(tab_id, 'terminal')
      if (prompt) useRunnerStore.getState().recordStagePrompt(prompt)
      const argv = Array.isArray(data.argv) ? (data.argv as string[]) : undefined
      const initialInput = isInteractive && prompt ? prompt : undefined
      void window.pathly.terminal.registerRunner(tab_id, topic, run_id, label)
        .then(() => window.pathly.terminal.spawn(tab_id, cwd, undefined, argv, initialInput))
        .then(() => {
          useTerminalStore.getState().updateTabStatus(tab_id, 'running')
          apiFetch('/runner/terminal/started', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tab_id, run_id, topic, pid: 0 }),
          }).catch((err) => console.error('[spawn] /runner/terminal/started failed', err))
        })
        .catch((err) => console.error('[spawn] PTY spawn failed for', tab_id, 'cwd=', cwd, err))
    }

    const killTerminal = (tabId: string | undefined): void => {
      const id = tabId ?? useRunnerStore.getState().activeRunnerTabId
      if (!id) return
      void window.pathly.terminal.kill(id).catch(() => { /* PTY may already be gone */ })
      xtermRegistry.dispose(id)
      useTerminalStore.getState().closeTab(id)
    }

    const connect = (): void => {
      try {
        es = new EventSource('http://127.0.0.1:8765/events/spawn')
        es.onopen = () => { retry = 0 }
        es.onmessage = (e: MessageEvent) => {
          try {
            const data = JSON.parse(e.data as string) as Record<string, unknown> & { type: string }
            if (data.type === 'TERMINAL_SPAWN') {
              openTerminal(data)
            } else if (data.type === 'TERMINAL_KILL') {
              killTerminal(data.tab_id as string | undefined)
            } else if (data.type === 'TERMINAL_SIGNAL' && data.signal === 'term') {
              killTerminal(data.tab_id as string | undefined)
            }
          } catch { /* ignore parse errors */ }
        }
        es.onerror = () => {
          es?.close()
          es = null
          const delay = Math.min(3000 * Math.pow(2, retry), 30000)
          retry += 1
          reconnectTimeout = setTimeout(connect, delay)
        }
      } catch { /* EventSource not available — silently skip */ }
    }

    connect()
    return () => {
      if (reconnectTimeout !== null) clearTimeout(reconnectTimeout)
      es?.close()
      exitUnsub()
      progressByTab.forEach((e) => e.stop())
      progressByTab.clear()
    }
  }, [])

  return null
}
