import { useState, useRef, useEffect, useCallback, type Dispatch, type SetStateAction } from 'react'
import { useProjectStore } from '../../../../store/projectStore'
import { useElapsedProgress, type ActionProgress } from '../../../shared/RunPill/progress'
import type { PillState } from '../../../shared/RunPill/RunPill'
import type { AiSelection } from '../../../../services/aiRouter'
import { runJobWithAbort, isOff } from '../../../../services/aiRouter'
import { buildSummarizePrompt } from '../../../../services/summaryPrompt'
import { composeClientSkill } from '../../../../services/skillCompose'
import { readFile } from '../../../../services/pathlyApi'
import { useCommsStore } from '../../../../store/commsStore'
import {
  fetchArtifacts,
  apiGetDefaultSelection,
  apiSetArtifactSummary,
  apiSetArtifactSelection,
  type ArtifactRow,
  type AiSelectionDto,
} from '../../../../store/commsApi'
import { parseSelection, isSummarizable } from '../ArtifactsView/summarizeArtifact'
import { resolveArtifactPath } from '../artifactPath'

// State for the ResummarizeButton pill (used on artifact cards and in the ArtifactModal
// footer). Owns: per-artifact selection (seeded from artifact row → app default),
// PillState, elapsed-progress timer, abort handle, and gear popover toggle.

const BUILTIN_DEFAULT: AiSelection = { type: 'engine', id: 'claude' }

// The CLI engine writes its summary to a sibling file (the file-based capture contract);
// we poll for it after the engine exits. Mirrors the editor's pollForFile cadence.
async function pollSummaryFile(path: string, tries = 5, delayMs = 600): Promise<string | null> {
  for (let i = 0; i < tries; i++) {
    if (i > 0) await new Promise<void>((r) => setTimeout(r, delayMs))
    const c = await readFile(path)
    if (c != null && c.trim()) return c
  }
  return null
}

export interface ResummarizeHook {
  pillState: PillState
  progress: ActionProgress | null
  selection: AiSelection
  setSelection: (sel: AiSelection) => void
  configOpen: boolean
  setConfigOpen: Dispatch<SetStateAction<boolean>>
  gearRef: React.RefObject<HTMLButtonElement>
  run: () => void
  stop: () => void
}

export function useResummarize(messageId: string): ResummarizeHook {
  const [pillState, setPillState] = useState<PillState>('idle')
  const [startedAt, setStartedAt] = useState<number | undefined>()
  const [configOpen, setConfigOpen] = useState(false)
  const [selection, setSelectionState] = useState<AiSelection>(BUILTIN_DEFAULT)
  const abortRef = useRef<(() => void) | null>(null)
  const gearRef = useRef<HTMLButtonElement>(null)
  const projectPath = useProjectStore((st) => st.projectPath)

  // Seed the per-artifact selection from the stored row, then fall back to app default.
  useEffect(() => {
    let alive = true
    void fetchArtifacts(messageId).then(async (rows) => {
      if (!alive) return
      const row: ArtifactRow | undefined = rows[0]
      if (!row) return
      const saved = parseSelection(row.summary_selection)
      if (saved) { setSelectionState(saved); return }
      const def = await apiGetDefaultSelection()
      if (alive && def) setSelectionState(def)
    })
    return () => { alive = false }
  }, [messageId])

  const progress = useElapsedProgress(startedAt)

  // Persist per-artifact selection immediately when the user changes it.
  const setSelection = useCallback((sel: AiSelection) => {
    setSelectionState(sel)
    void fetchArtifacts(messageId).then((rows) => {
      const row: ArtifactRow | undefined = rows[0]
      if (row) void apiSetArtifactSelection(row.id, sel as AiSelectionDto)
    })
  }, [messageId])

  function run(): void {
    if (pillState === 'running') return
    setPillState('running')
    setStartedAt(Date.now())
    // Drive the per-artifact badge + toast (📝 ready / ⚠ failed). markSummaryStatus owns
    // the toasts, so this hook never pushes its own — one feedback source, no double toast.
    const markStatus = useCommsStore.getState().markSummaryStatus
    markStatus(messageId, 'summarizing')

    void (async () => {
      try {
        const rows = await fetchArtifacts(messageId)
        const row: ArtifactRow | undefined = rows[0]
        if (!row) throw new Error('Artifact not found')
        if (isOff(selection)) { setPillState('idle'); setStartedAt(undefined); return }
        const name = row.path.split(/[/\\]/).pop() ?? row.path
        if (!isSummarizable(row.type ?? undefined, name)) {
          setPillState('idle'); setStartedAt(undefined); return
        }

        const abs = resolveArtifactPath(row.path, projectPath)
        const text = await readFile(abs)
        if (text == null) throw new Error(`File not found: ${abs}`)
        if (!text.trim()) throw new Error('File is empty')

        const cwd = projectPath.replace(/\\/g, '/').replace(/\/$/, '') || undefined

        // Bare path: send buildSummarizePrompt and read the result text. Used for MODEL
        // targets (they return clean text directly — left untouched, their own plan) and
        // as the fallback when the /skills/compose endpoint is unreachable.
        const runBare = async (): Promise<string> => {
          const { promise, abort } = runJobWithAbort(
            { kind: 'summarize', prompt: buildSummarizePrompt(text), cwd },
            selection,
          )
          abortRef.current = abort
          const result = await promise
          abortRef.current = null
          return (result.text ?? '').trim()
        }

        let summary: string
        if (selection.type === 'engine') {
          // CLI ENGINE: compose the fragment-based prompt and have the engine WRITE its
          // summary to a sibling file, then read that file — no stdout-tail scraping (that
          // was the codex-chrome / claude-flattening bug). Falls back to bare on null.
          const outAbs = `${abs}.summary`
          const composed = await composeClientSkill(
            'development/summarize',
            selection.id,
            { source_path: abs, out_path: outAbs, kind: 'summary' },
            { projectRoot: cwd },
          )
          if (composed) {
            const { promise, abort } = runJobWithAbort({ kind: 'summarize', prompt: composed, cwd }, selection)
            abortRef.current = abort
            await promise // ignore the stdout tail — the file is the result
            abortRef.current = null
            const fileText = await pollSummaryFile(outAbs)
            if (fileText == null) throw new Error('the engine did not write the summary file')
            const trimmed = fileText.trim()
            if (/^ERROR:/i.test(trimmed)) {
              throw new Error(trimmed.replace(/^ERROR:\s*/i, '') || 'the engine reported an error')
            }
            summary = trimmed
          } else {
            summary = await runBare()
          }
        } else {
          summary = await runBare()
        }

        // Empty output is a failure, not a silent success — otherwise the pill says
        // "done" but nothing is saved and the card looks unchanged.
        if (!summary) throw new Error('the engine returned no summary text')
        await apiSetArtifactSummary(row.id, summary, selection as AiSelectionDto)

        markStatus(messageId, 'ready')
        setPillState('done')
        setStartedAt(undefined)
        window.setTimeout(() => setPillState((s) => (s === 'done' ? 'idle' : s)), 2000)
      } catch (err: unknown) {
        abortRef.current = null
        const msg = err instanceof Error ? err.message : String(err)
        if (msg === 'aborted') {
          setPillState('idle')
          setStartedAt(undefined)
        } else {
          markStatus(messageId, 'failed', msg)
          setPillState('error')
          setStartedAt(undefined)
          window.setTimeout(() => setPillState((s) => (s === 'error' ? 'idle' : s)), 2500)
        }
      }
    })()
  }

  function stop(): void {
    abortRef.current?.()
    abortRef.current = null
    setPillState('idle')
    setStartedAt(undefined)
  }

  return { pillState, progress, selection, setSelection, configOpen, setConfigOpen, gearRef, run, stop }
}
