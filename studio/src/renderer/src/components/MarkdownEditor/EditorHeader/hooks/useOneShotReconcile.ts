import { useEffect } from 'react'
import { useUiStore, type MdEditorAction } from '../../../../store/uiStore'
import { useTerminalStore } from '../../../../store/terminalStore'

// Reload-resilient liveness reconcile for a single MD-editor one-shot slot (Split / Analyze /
// Diagram) — the editor-side analogue of commsStore.rehydrateActiveRuns for the board pills.
//
// Why it exists: `mdEditorActions` is now PERSISTED (uiStore), so a running slot survives a full
// renderer reload — but the run's completion handler is a per-spawn `onExit` CLOSURE that a reload
// destroys, so an orphaned slot would otherwise spin forever. This reconciles the persisted slot
// against the AUTHORITATIVE live gate-engine list (main-process-owned → survives reload), which is
// the same liveness source the CLI monitor uses.
//
// Two correctness guards:
//  1. It queries `terminal.getEngines()` (a direct snapshot) rather than the pushed `spawn:state`
//     list, which arrives empty-then-populated after a reload and would race a reconcile into
//     false-clearing a run that is actually still alive. The pushed list is used only as the
//     re-run TRIGGER (so an exit while the app is open also clears the pill).
//  2. When the engine is gone it waits a short grace period and re-checks before clearing — so a
//     NORMAL in-session completion (whose onExit sets success/error, arriving on a separate IPC
//     tick from the engine removal) always wins; only a genuinely orphaned 'running' slot is cleared.
//
// Fail-safe: the worst case is a pill CLEARS (as it did before persistence existed) — never a stuck pill.
export function useOneShotReconcile(mdEditorPath: string | null, action: MdEditorAction): void {
  const setMdEditorAction = useUiStore((s) => s.setMdEditorAction)
  // Trigger only — re-verify whenever the live engine set changes (e.g. a run exits).
  const engines = useTerminalStore((s) => s.spawnQueue.engines)

  useEffect(() => {
    if (!mdEditorPath) return
    const slot = useUiStore.getState().mdEditorActions[mdEditorPath]?.[action]
    if (slot?.status !== 'running' || !slot.tabId) return
    const tabId = slot.tabId
    let cancelled = false
    let graceTimer: number | undefined

    void window.pathly.terminal.getEngines().then((live) => {
      if (cancelled) return
      if (live.some((e) => e.tabId === tabId)) return // still alive → keep the pill running
      // Engine gone. Give a normal onExit (success/error, on its own IPC tick) time to land;
      // only clear if the slot is STILL 'running' with the same tab after the grace window —
      // i.e. it was orphaned by a reload (its onExit closure died), not completing normally.
      graceTimer = window.setTimeout(() => {
        const cur = useUiStore.getState().mdEditorActions[mdEditorPath]?.[action]
        if (cur?.status === 'running' && cur.tabId === tabId) setMdEditorAction(mdEditorPath, action, null)
      }, 2500)
    })

    return () => { cancelled = true; if (graceTimer) window.clearTimeout(graceTimer) }
  }, [mdEditorPath, action, engines, setMdEditorAction])
}
