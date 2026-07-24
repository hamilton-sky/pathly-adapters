import { useCallback, useEffect } from 'react'
import { useTerminalStore } from '../../../../store/terminalStore'
import { useUiStore } from '../../../../store/uiStore'
import type { TerminalTab } from '../../../../store/terminalStore'
import { useToastStore } from '../../../../store/toastStore'
import { buildSplitPrompt, getSpawnCwd, STORAGE_KEY_SPLIT, describeAgentFailure } from '../../../Editor/commentUtils'
import { buildCliArgv, cliLabel, EditorCli } from '../editorCli'
import { composeClientSkill } from '../../../../services/skillCompose'
import { attachProgress } from '../editorProgress'

// Resolve the AI-Split prompt. Precedence: explicit one-time prompt > stored override
// (the user's customization) > composed fragment skill (the default — same fragments the
// board actions use) > bare builder (fallback when /skills/compose is unreachable).
//
// AI-Analyze no longer lives here — it went multi-report and moved to useEditorAnalysisAction
// (lens presets carry the full append-contract prompt; no composeClientSkill).
async function resolveSplitPrompt(
  once: string | null | undefined,
  cli: EditorCli,
  source: string,
  outPath: string,
): Promise<string> {
  if (once) return once
  let stored: string | null = null
  try { stored = localStorage.getItem(STORAGE_KEY_SPLIT) } catch { stored = null }
  if (stored) return stored
  const composed = await composeClientSkill(
    'development/split',
    cli,
    { source_path: source.replace(/\\/g, '/'), out_path: outPath.replace(/\\/g, '/'), kind: 'split' },
    { projectRoot: getSpawnCwd(source) },
  )
  return composed ?? buildSplitPrompt(source)
}

// True when the agent wrote an `ERROR:`-prefixed file (the client-file-output failure contract).
function isErrorResult(content: string | null): boolean {
  return content != null && /^ERROR:/i.test(content.trim())
}

const toast = (msg: string, variant: 'info' | 'success' | 'error', category: 'phase_summary' | 'agent_done') =>
  useToastStore.getState().push(msg, variant, { category })

async function pollForFile(path: string): Promise<string | null> {
  for (let i = 0; i < 5; i++) {
    if (i > 0) await new Promise<void>((r) => setTimeout(r, 600))
    const content = await window.pathly.fs.read(path)
    if (content != null && content !== '') return content
  }
  return null
}

// All run state lives in uiStore.mdEditorActions, keyed by the file that started the run.
// This hook is a single shared instance (EditorHeader does not remount on navigation),
// so it MUST NOT hold any per-run React state — every read/write is keyed by the captured
// `forFile`, so a run completing while the user is on another file never touches the visible
// file's pill. The header derives the visible file's state via selectMdEditorSplit.
export function useEditorAgentActions(
  mdEditorPath: string | null,
  splitOncePrompt: string | null,
  onSplitOnceUsed: () => void,
  splitCli: EditorCli,
) {
  const addTab  = useTerminalStore((s) => s.addTab)
  const openTab = useTerminalStore((s) => s.openTab)
  const setMdEditorSplitDraftPath = useUiStore((s) => s.setMdEditorSplitDraftPath)
  const setMdEditorViewMode      = useUiStore((s) => s.setMdEditorViewMode)
  const setMdEditorAction        = useUiStore((s) => s.setMdEditorAction)
  // Subscribe to the tab list so the reconciliation effect below re-runs on add/remove.
  const tabs = useTerminalStore((s) => s.tabs)

  // Stale-run reconciliation: if the visible file has a split slot still marked 'running' but
  // its terminal tab has vanished (closed manually, or a backend exit we never received), reset
  // it so the pill can't spin forever. Zero false positives — a healthy run keeps its tab in the
  // store until onExit closes it, and completed runs are status 'success'/'error', not 'running'.
  useEffect(() => {
    if (!mdEditorPath) return
    const slot = useUiStore.getState().mdEditorActions[mdEditorPath]?.split
    if (slot?.status === 'running' && slot.tabId && !tabs.some((t) => t.id === slot.tabId)) {
      setMdEditorAction(mdEditorPath, 'split', null)
    }
  }, [mdEditorPath, tabs, setMdEditorAction])

  // Clear a slot back to idle, but only if it still holds the transient state we set —
  // never clobber a newer run that started on the same file in the meantime.
  const clearIfStill = useCallback(
    (forFile: string, tabId: string) => {
      const slot = useUiStore.getState().mdEditorActions[forFile]?.split
      // Only clear if THIS exact run still owns the slot — a newer run (running or completed)
      // carries a different tabId, so its terminal success/error is never wiped early.
      if (slot && slot.status !== 'running' && slot.tabId === tabId) setMdEditorAction(forFile, 'split', null)
    },
    [setMdEditorAction],
  )

  const handleSplit = useCallback(async (promptOverride?: string) => {
    const forFile = mdEditorPath
    if (!forFile) return
    if (useUiStore.getState().mdEditorActions[forFile]?.split?.status === 'running') return
    const draftPath = forFile + '.split.draft'
    const norm = forFile.replace(/\\/g, '/')
    const fileName = norm.split('/').pop() ?? 'skill'
    const tabId = `split-${Date.now().toString(36)}`
    const prompt = await resolveSplitPrompt(promptOverride ?? splitOncePrompt, splitCli, forFile, draftPath)
    addTab(tabId, `Split · ${fileName}`, 'left', splitCli as TerminalTab['kind'], undefined, undefined, prompt)
    // Optimistic running BEFORE the spawn await so startedAt is stamped at t0 (the elapsed
    // timer derives from tab.startedAt) and a quick navigate-away-and-back restores the pill.
    useTerminalStore.getState().updateTabStatus(tabId, 'running')
    setMdEditorAction(forFile, 'split', { status: 'running', tabId, stopping: false })
    openTab(tabId)
    toast(`AI Split started · ${fileName} (${cliLabel(splitCli)})`, 'info', 'phase_summary')
    // attachProgress drives only the milestone toasts now; the pill's timer is derived from
    // tab.startedAt in the header, so we discard the per-tick progress payload.
    const stopProgress = attachProgress(tabId, () => {}, (line) => toast(`Split: ${line}`, 'info', 'phase_summary'))
    const unsubscribe = window.pathly.terminal.onExit((exitedTabId: string, exitCode?: number, tail?: string) => {
      if (exitedTabId !== tabId) return
      unsubscribe()
      stopProgress()
      // If this run's slot is gone or replaced — e.g. the user hit Stop, which closes the tab
      // and clears the slot synchronously — this exit was already handled. No-op.
      const live = useUiStore.getState().mdEditorActions[forFile]?.split
      if (!live || live.tabId !== tabId) return
      void pollForFile(draftPath).then(async (content) => {
        if (content != null && !isErrorResult(content)) {
          // A draft that byte-matches the source is a no-op split — the agent rewrote the file
          // unchanged. Registering it would light the Diff pill onto an empty diff that opens and
          // instantly closes (nothing to review — the "flicker and vanish"); instead delete the
          // stale draft, leave the pill dark, and report the no-op honestly.
          const original = await window.pathly.fs.read(forFile)
          const noChanges = original != null && original === content
          useTerminalStore.getState().updateTabStatus(tabId, 'done')
          useTerminalStore.getState().closeTab(tabId)
          if (noChanges) {
            void window.pathly.fs.delete(draftPath)
            setMdEditorSplitDraftPath(null, forFile)
            setMdEditorAction(forFile, 'split', { status: 'success', tabId, stopping: false })
            toast(`AI Split made no changes · ${fileName}`, 'info', 'agent_done')
          } else {
            setMdEditorSplitDraftPath(draftPath, forFile)
            if (useUiStore.getState().mdEditorPath === forFile) setMdEditorViewMode('editor')
            setMdEditorAction(forFile, 'split', { status: 'success', tabId, stopping: false })
            toast(`AI Split ready · ${fileName} — review the diff`, 'success', 'agent_done')
          }
          setTimeout(() => clearIfStill(forFile, tabId), 3000)
        } else {
          useTerminalStore.getState().updateTabStatus(tabId, 'error')
          useTerminalStore.getState().closeTab(tabId)
          setMdEditorAction(forFile, 'split', { status: 'error', tabId, stopping: false })
          // An ERROR:-prefixed file carries the agent's own reason; otherwise it never wrote one.
          const reason = content != null && isErrorResult(content)
            ? content.trim().replace(/^ERROR:\s*/i, '') || 'the agent reported an error'
            : null
          toast(reason ? `AI Split failed · ${fileName} — ${reason}` : describeAgentFailure('AI Split', fileName, exitCode, tail), 'error', 'agent_done')
          setTimeout(() => clearIfStill(forFile, tabId), 3000)
        }
      })
    })
    try {
      await window.pathly.terminal.spawn(tabId, getSpawnCwd(forFile), undefined, buildCliArgv(splitCli, prompt), undefined, {
        telemetry: { scopeTier: 'project', label: 'ai-split', role: 'splitter' },
      })
      onSplitOnceUsed()
    } catch (e) {
      unsubscribe()
      stopProgress()
      const slot = useUiStore.getState().mdEditorActions[forFile]?.split
      if ((e instanceof Error && /cancelled/i.test(e.message)) || !slot || slot.tabId !== tabId) {
        // Cancelled from the queue (or already finalized) — clean up quietly, no error toast.
        useTerminalStore.getState().closeTab(tabId)
        setMdEditorAction(forFile, 'split', null)
        return
      }
      useTerminalStore.getState().updateTabStatus(tabId, 'error')
      useTerminalStore.getState().closeTab(tabId)
      setMdEditorAction(forFile, 'split', { status: 'error', tabId, stopping: false })
      toast(`AI Split failed · ${fileName} — could not launch ${cliLabel(splitCli)}`, 'error', 'agent_done')
      setTimeout(() => clearIfStill(forFile, tabId), 3000)
    }
  }, [mdEditorPath, splitOncePrompt, onSplitOnceUsed, addTab, openTab, setMdEditorSplitDraftPath, setMdEditorViewMode, setMdEditorAction, clearIfStill, splitCli])

  // Stop closes the tab IMMEDIATELY (like the terminal's own close button) rather than waiting
  // for onExit — a force-killed PTY (taskkill /T /F) may never deliver a clean exit event.
  // Clearing the slot makes the run's onExit a no-op if it does fire later.
  const stopSplit = useCallback(() => {
    const forFile = mdEditorPath
    if (!forFile) return
    const tabId = useUiStore.getState().mdEditorActions[forFile]?.split?.tabId
    if (!tabId) return
    void window.pathly.terminal.kill(tabId)
    useTerminalStore.getState().updateTabStatus(tabId, 'done')
    useTerminalStore.getState().closeTab(tabId)
    setMdEditorAction(forFile, 'split', null)
    const fileName = forFile.replace(/\\/g, '/').split('/').pop() ?? 'file'
    toast(`AI Split stopped · ${fileName}`, 'info', 'phase_summary')
  }, [mdEditorPath, setMdEditorAction])

  return { handleSplit, stopSplit }
}
