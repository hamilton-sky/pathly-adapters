import { useState, useRef, useEffect, useCallback, type Dispatch, type SetStateAction } from 'react'
import { useProjectStore } from '../../../../store/projectStore'
import { useElapsedProgress, type ActionProgress } from '../../../shared/RunPill/progress'
import type { PillState } from '../../../shared/RunPill/RunPill'
import type { AiSelection } from '../../../../services/aiRouter'
import { runJobWithAbort, isOff } from '../../../../services/aiRouter'
import { buildSummarizePrompt, parseStructuredSummary } from '../../../../services/summaryPrompt'
import { composeClientSkill } from '../../../../services/skillCompose'
import { readFile, deleteFile } from '../../../../services/pathlyApi'
import { useCommsStore } from '../../../../store/commsStore'
import {
  fetchArtifacts,
  apiGetDefaultSelection,
  apiSetArtifactSummary,
  apiEditMessage,
  apiSetArtifactSelection,
  apiSetArtifactStyle,
  apiSetArtifactNote,
  SUMMARY_STYLE_DEFAULT,
  type ArtifactRow,
  type AiSelectionDto,
  type SummaryStyle,
} from '../../../../store/commsApi'
import { parseSelection, isSummarizable, STYLE_SKILL, pollSummaryFile, stripAnsi } from '../ArtifactsView/summarizeArtifact'
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
  style: SummaryStyle
  setStyle: (style: SummaryStyle) => void
  note: string
  setNote: (note: string) => void
  configOpen: boolean
  setConfigOpen: Dispatch<SetStateAction<boolean>>
  gearRef: React.RefObject<HTMLButtonElement>
  /** The confirm-before-send preview ({ prompt, fileName }) — null until prepared. */
  preview: { prompt: string; fileName: string } | null
  confirmOpen: boolean
  setConfirmOpen: Dispatch<SetStateAction<boolean>>
  /** Build the preview and open the confirm modal (does NOT spawn — run() does). */
  prepareRun: () => void
  run: () => void
  stop: () => void
}

export function useResummarize(messageId: string): ResummarizeHook {
  const [pillState, setPillState] = useState<PillState>('idle')
  const [startedAt, setStartedAt] = useState<number | undefined>()
  const [configOpen, setConfigOpen] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [preview, setPreview] = useState<{ prompt: string; fileName: string } | null>(null)
  const [selection, setSelectionState] = useState<AiSelection>(BUILTIN_DEFAULT)
  const [style, setStyleState] = useState<SummaryStyle>(SUMMARY_STYLE_DEFAULT)
  const [note, setNoteState] = useState('')
  // run() reads the note from a ref so a value set on the textarea's blur (which fires on
  // the same click that triggers Summarize) is never missed by a stale closure.
  const noteRef = useRef('')
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
      if (row.summary_style) setStyleState(row.summary_style)
      if (row.summary_note) { setNoteState(row.summary_note); noteRef.current = row.summary_note }
      // Local models are a separate system (chat only) — a summary always runs on a CLI agent so it
      // goes through the gate. Coerce any stored local-model target to the default CLI adapter
      // (Off is preserved). New picks are already CLI-only (the selector no longer lists locals).
      const cliOnly = (sel: AiSelection): AiSelection =>
        sel.type === 'model' && !isOff(sel) ? { type: 'engine', id: 'claude' } : sel
      const saved = parseSelection(row.summary_selection)
      if (saved) { setSelectionState(cliOnly(saved)); return }
      const def = await apiGetDefaultSelection()
      if (alive && def) setSelectionState(cliOnly(def))
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

  // Persist per-artifact summary DEPTH style immediately when the user changes it.
  const setStyle = useCallback((next: SummaryStyle) => {
    setStyleState(next)
    void fetchArtifacts(messageId).then((rows) => {
      const row: ArtifactRow | undefined = rows[0]
      if (row) void apiSetArtifactStyle(row.id, next)
    })
  }, [messageId])

  // Persist the per-artifact "special request" note (debounced by the popover's blur/run).
  const setNote = useCallback((next: string) => {
    setNoteState(next)
    noteRef.current = next
    void fetchArtifacts(messageId).then((rows) => {
      const row: ArtifactRow | undefined = rows[0]
      if (row) void apiSetArtifactNote(row.id, next)
    })
  }, [messageId])

  // Build the exact prompt that run() will send and open the confirm modal — the
  // preview→Cancel/Submit gate, matching Decompose/Evaluate. Does NOT spawn; run() does.
  function prepareRun(): void {
    if (pillState === 'running') return
    void (async () => {
      try {
        const rows = await fetchArtifacts(messageId)
        const row: ArtifactRow | undefined = rows[0]
        if (!row || isOff(selection)) return
        const name = row.path.split(/[/\\]/).pop() ?? row.path
        if (!isSummarizable(row.type ?? undefined, name)) return
        const abs = resolveArtifactPath(row.path, projectPath)
        const cwd = projectPath.replace(/\\/g, '/').replace(/\/$/, '') || undefined
        const noteSuffix = noteRef.current.trim()
          ? `\n\n## Additional request from the user\n${noteRef.current.trim()}`
          : ''
        let prompt: string | null = null
        if (selection.type === 'engine') {
          prompt = await composeClientSkill(
            STYLE_SKILL[style],
            selection.id,
            { source_path: abs, out_path: `${abs}.summary`, kind: 'summary' },
            { projectRoot: cwd },
          )
        }
        if (prompt == null) {
          const text = await readFile(abs)
          prompt = buildSummarizePrompt(text ?? '', style)
        }
        setPreview({ prompt: prompt + noteSuffix, fileName: name })
        setConfirmOpen(true)
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err)
        useCommsStore.getState().markSummaryStatus(messageId, 'failed', msg)
      }
    })()
  }

  function run(): void {
    if (pillState === 'running') return
    setPillState('running')
    setStartedAt(Date.now())
    // Drive the per-artifact badge + toast (ready / failed). markSummaryStatus owns
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

        // The per-artifact "special request" is appended to whatever prompt runs (composed
        // or bare). It lands mid-prompt, after the dash-safe composed body, so it can never
        // break argv parsing.
        const noteSuffix = noteRef.current.trim()
          ? `\n\n## Additional request from the user\n${noteRef.current.trim()}`
          : ''

        // Bare path: send buildSummarizePrompt and read the result text. Used for MODEL
        // targets (they return clean text directly — left untouched, their own plan) and
        // as the fallback when the /skills/compose endpoint is unreachable.
        const runBare = async (): Promise<string> => {
          const { promise, abort } = runJobWithAbort(
            { kind: 'summarize', prompt: buildSummarizePrompt(text, style) + noteSuffix, cwd },
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
            STYLE_SKILL[style],
            selection.id,
            { source_path: abs, out_path: outAbs, kind: 'summary' },
            { projectRoot: cwd },
          )
          if (composed) {
            const { promise, abort } = runJobWithAbort({ kind: 'summarize', prompt: composed + noteSuffix, cwd }, selection)
            abortRef.current = abort
            await promise // ignore the stdout tail — the file is the result
            abortRef.current = null
            const fileText = await pollSummaryFile(outAbs)
            if (fileText == null) throw new Error('the engine did not write the summary file')
            // The .summary file is a transient capture handoff — we've read it into memory and
            // the comms_artifacts row is the record. Delete it best-effort so capture files
            // don't accumulate on disk (the editor's .analysis/.draft are user-facing and keep
            // their own accept/reject lifecycle, so this applies to summaries only).
            void deleteFile(outAbs).catch(() => {})
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

        // Strip any leaked terminal escape codes (the stdout-tail fallback path), then
        // treat empty output as a failure — not a silent "done" with nothing saved.
        summary = stripAnsi(summary)
        if (!summary) throw new Error('the engine returned no summary text')
        // Split the structured result: Description refreshes the artifact's message text (the
        // card's "Description"); the Summary body goes to comms_artifacts.summary. Edit the
        // description FIRST so the summary write's re-embed (description + summary) sees it.
        const { description, summary: summaryBody } = parseStructuredSummary(summary)
        if (description) await apiEditMessage(messageId, description)
        await apiSetArtifactSummary(row.id, summaryBody, selection as AiSelectionDto)

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

  return { pillState, progress, selection, setSelection, style, setStyle, note, setNote, configOpen, setConfigOpen, gearRef, preview, confirmOpen, setConfirmOpen, prepareRun, run, stop }
}
