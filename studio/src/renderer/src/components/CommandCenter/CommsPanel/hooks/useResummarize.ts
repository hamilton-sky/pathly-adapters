import { useState, useRef, useEffect, useCallback, type Dispatch, type SetStateAction } from 'react'
import { useProjectStore } from '../../../../store/projectStore'
import { useElapsedProgress, type ActionProgress } from '../../../shared/RunPill/progress'
import type { PillState } from '../../../shared/RunPill/RunPill'
import type { AiSelection } from '../../../../services/aiRouter'
import { runJobWithAbort, isOff } from '../../../../services/aiRouter'
import { buildSummarizePrompt } from '../../../../services/summaryPrompt'
import { readFile } from '../../../../services/pathlyApi'
import { useToastStore } from '../../../../store/toastStore'
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
        const { promise, abort } = runJobWithAbort(
          { kind: 'summarize', prompt: buildSummarizePrompt(text), cwd },
          selection,
        )
        abortRef.current = abort

        const result = await promise
        abortRef.current = null

        const summary = (result.text ?? '').trim()
        if (summary) await apiSetArtifactSummary(row.id, summary, selection as AiSelectionDto)

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
          useToastStore.getState().push(`Re-summarize failed: ${msg}`, 'error', { category: 'agent_done' })
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
