import React, { useState, useRef, useEffect, useCallback } from 'react'
import { useToastStore } from '../../../store/toastStore'
import {
  ArrowLeft, Undo2, Redo2, Database, FileCode, BookOpen,
  ScanText, FileSearch, Scissors, Wand2, GitCompare,
  // ── Diagram feature ──
  Network, Image as ImageIcon,
} from 'lucide-react'
import { Tooltip } from '../../ui'
import { useMarkdownEditorStore, BodyCell } from '../../../store/markdownEditorStore'
import { useProjectStore } from '../../../store/projectStore'
import {
  useUiStore,
  selectMdEditorSplitDraftPath, selectMdEditorAnalysisPath, selectMdEditorSplit, selectMdEditorAnalyze,
  // ── Diagram feature ──
  selectMdEditorDiagramPath, selectMdEditorDiagram,
} from '../../../store/uiStore'
import { useTerminalStore } from '../../../store/terminalStore'
import { useEditorAgentActions } from './hooks/useEditorAgentActions'
import { useEditorAnalysisAction } from './hooks/useEditorAnalysisAction'
import { apiFetch } from '../../../lib/config'
import { STORAGE_KEY_SPLIT, STORAGE_KEY_ANALYZE, getEffectivePrompt, buildSplitPrompt } from '../../Editor/commentUtils'
import PromptPeekModal from './PromptPeekModal/PromptPeekModal'
import ExportMenu from './ExportMenu/ExportMenu'
import ActionPill from '../../shared/ActionPill/ActionPill'
import { loadEditorCli, saveEditorCli, EditorCli, cliLabel, CLI_KEY_SPLIT, CLI_KEY_ANALYZE, loadPreset, savePreset, PRESET_KEY_SPLIT, PRESET_KEY_ANALYZE } from './editorCli'
import { SPLIT_PRESETS, ANALYZE_LENSES } from './actionPresets'
import { useElapsedProgress } from './editorProgress'
import SkillSplitModal from '../../shared/SkillSplitModal/SkillSplitModal'
import SendPreviewModal from '../../shared/SendPreviewModal/SendPreviewModal'
// ── Diagram feature ──
import { useEditorDiagramAction } from './hooks/useEditorDiagramAction'
import { DIAGRAM_PRESETS, CLI_KEY_DIAGRAM, PRESET_KEY_DIAGRAM, STORAGE_KEY_DIAGRAM } from './diagramPresets'
import { resolvePrompt } from '../../shared/PromptActionConfig/presetTypes'
import { sidecarPathFor } from '../diagramTypes'
import { analysisSidecarPathFor } from '../analysisTypes'
import styles from './EditorHeader.module.css'

export type MdEditorViewMode = 'cells' | 'editor'

interface Props {
  viewMode: MdEditorViewMode
  onToggleViewMode: () => void
}

export default function EditorHeader({ viewMode, onToggleViewMode }: Props) {
  const { undo, redo, cells, historyIndex, savedHistoryIndex, history, markCellsSaved, insertBodyCell, frontmatterRaw } = useMarkdownEditorStore()

  const mdEditorPath         = useUiStore(s => s.mdEditorPath)
  const setMdEditorPath      = useUiStore(s => s.setMdEditorPath)
  const setMdEditorViewMode  = useUiStore(s => s.setMdEditorViewMode)
  const dirtyItems                = useUiStore(s => s.dirtyItems)
  const mdEditorSplitDraftPath    = useUiStore(selectMdEditorSplitDraftPath)
  const requestMdEditorSave       = useUiStore(s => s.requestMdEditorSave)
  const requestMdEditorOpenDraft  = useUiStore(s => s.requestMdEditorOpenDraft)
  const requestMdEditorUndo       = useUiStore(s => s.requestMdEditorUndo)
  const requestMdEditorRedo       = useUiStore(s => s.requestMdEditorRedo)
  const mdEditorAnalysisPath       = useUiStore(selectMdEditorAnalysisPath)
  const mdEditorAnalysisPanelOpen  = useUiStore(s => s.mdEditorAnalysisPanelOpen)
  const setMdEditorAnalysisPanelOpen = useUiStore(s => s.setMdEditorAnalysisPanelOpen)
  // ── Diagram feature ──
  const mdEditorDiagramPath        = useUiStore(selectMdEditorDiagramPath)
  const mdEditorDiagramPanelOpen   = useUiStore(s => s.mdEditorDiagramPanelOpen)
  const setMdEditorDiagramPanelOpen = useUiStore(s => s.setMdEditorDiagramPanelOpen)

  const [exportState, setExportState] = useState<'idle' | 'success' | 'error'>('idle')
  const [saveState,   setSaveState]   = useState<'idle' | 'success' | 'error'>('idle')
  const [splitPeekOpen,    setSplitPeekOpen]    = useState(false)
  const [splitCellsOpen,   setSplitCellsOpen]   = useState(false)
  const [analyzePeekOpen,  setAnalyzePeekOpen]  = useState(false)
  const [splitOncePrompt,  setSplitOncePrompt]  = useState<string | null>(null)
  const [analyzeOncePrompt, setAnalyzeOncePrompt] = useState<string | null>(null)
  const [splitCli,   setSplitCli]   = useState<EditorCli>(() => loadEditorCli(CLI_KEY_SPLIT))
  const [analyzeCli, setAnalyzeCli] = useState<EditorCli>(() => loadEditorCli(CLI_KEY_ANALYZE))
  const [splitPreset,   setSplitPreset]   = useState<string>(() => loadPreset(PRESET_KEY_SPLIT))
  const [analyzePreset, setAnalyzePreset] = useState<string>(() => loadPreset(PRESET_KEY_ANALYZE))
  // ── Diagram feature state ──
  const [diagramPeekOpen,  setDiagramPeekOpen]  = useState(false)
  const [diagramOncePrompt, setDiagramOncePrompt] = useState<string | null>(null)
  const [diagramCli,    setDiagramCli]    = useState<EditorCli>(() => loadEditorCli(CLI_KEY_DIAGRAM))
  const [diagramPreset, setDiagramPreset] = useState<string>(() => loadPreset(PRESET_KEY_DIAGRAM))
  // Confirm-before-send: holds the action + previewed prompt while the modal is open.
  const [pendingRun, setPendingRun] = useState<{ kind: 'split' | 'analyze' | 'diagram'; prompt: string; engine: string; action: string } | null>(null)

  const handleSplitCli   = (next: EditorCli) => { setSplitCli(next);   saveEditorCli(CLI_KEY_SPLIT, next) }
  const handleAnalyzeCli = (next: EditorCli) => { setAnalyzeCli(next); saveEditorCli(CLI_KEY_ANALYZE, next) }
  const handleDiagramCli = (next: EditorCli) => { setDiagramCli(next); saveEditorCli(CLI_KEY_DIAGRAM, next) }

  const handleSplitPreset = (name: string) => { setSplitPreset(name); savePreset(PRESET_KEY_SPLIT, name) }
  const handleAnalyzePreset = (name: string) => { setAnalyzePreset(name); savePreset(PRESET_KEY_ANALYZE, name) }
  const handleDiagramPreset = (name: string) => { setDiagramPreset(name); savePreset(PRESET_KEY_DIAGRAM, name) }

  // Pill titles follow the selected preset/lens, so the toolbar reflects what each run will do.
  const splitTitle   = SPLIT_PRESETS.find((p) => p.name === splitPreset)?.label ?? 'AI Split'
  const analyzeTitle = ANALYZE_LENSES.find((l) => l.name === analyzePreset)?.label ?? 'AI Analyze'
  const diagramTitle = DIAGRAM_PRESETS.find((p) => p.name === diagramPreset)?.label ?? 'Diagram'

  const { handleSplit, stopSplit } = useEditorAgentActions(
    mdEditorPath,
    splitOncePrompt,
    () => setSplitOncePrompt(null),
    splitCli,
  )

  // AI-Analyze is multi-report now (mirrors Diagram): each run appends a report to the
  // `.analyses.json` sidecar via a dedicated spawn hook, not the split/composeClientSkill path.
  const { handleAnalyze, stopAnalyze } = useEditorAnalysisAction(
    mdEditorPath,
    analyzeOncePrompt,
    () => setAnalyzeOncePrompt(null),
    analyzeCli,
    analyzePreset,
  )

  // ── Diagram feature: spawn hook ──
  const { handleDiagram, stopDiagram } = useEditorDiagramAction(
    mdEditorPath,
    diagramOncePrompt,
    () => setDiagramOncePrompt(null),
    diagramCli,
    diagramPreset,
  )

  // Resolve the diagram prompt for the preview: stored override > selected preset, with
  // {{FILE}} and {{SIDECAR}} substituted. (The peek modal only pre-fills {{FILE}}.)
  const buildDiagramPreviewPrompt = (filePath: string): string => {
    const norm = filePath.replace(/\\/g, '/')
    const vars = { FILE: norm, SIDECAR: sidecarPathFor(norm) }
    let template: string
    try {
      template = localStorage.getItem(STORAGE_KEY_DIAGRAM) ?? ''
    } catch {
      template = ''
    }
    if (!template) {
      template = (DIAGRAM_PRESETS.find((p) => p.name === diagramPreset) ?? DIAGRAM_PRESETS[0]).prompt
    }
    return resolvePrompt(template, vars)
  }

  // Resolve the analyze prompt for the preview: stored override > selected lens, with
  // {{FILE}} and {{SIDECAR}} substituted (mirrors buildDiagramPreviewPrompt).
  const buildAnalyzePreviewPrompt = (filePath: string): string => {
    const norm = filePath.replace(/\\/g, '/')
    const vars = { FILE: norm, SIDECAR: analysisSidecarPathFor(norm) }
    let template: string
    try {
      template = localStorage.getItem(STORAGE_KEY_ANALYZE) ?? ''
    } catch {
      template = ''
    }
    if (!template) {
      template = (ANALYZE_LENSES.find((l) => l.name === analyzePreset) ?? ANALYZE_LENSES[0]).prompt
    }
    return resolvePrompt(template, vars)
  }

  // Open the confirm-preview for a run; the actual spawn fires only on submit.
  const openSplitPreview = () => {
    if (!mdEditorPath) return
    const prompt = splitOncePrompt ?? getEffectivePrompt(buildSplitPrompt, STORAGE_KEY_SPLIT, mdEditorPath)
    setPendingRun({ kind: 'split', prompt, engine: cliLabel(splitCli), action: splitTitle })
  }
  const openAnalyzePreview = () => {
    if (!mdEditorPath) return
    const norm = mdEditorPath.replace(/\\/g, '/')
    const vars = { FILE: norm, SIDECAR: analysisSidecarPathFor(norm) }
    const prompt = analyzeOncePrompt ? resolvePrompt(analyzeOncePrompt, vars) : buildAnalyzePreviewPrompt(mdEditorPath)
    setPendingRun({ kind: 'analyze', prompt, engine: cliLabel(analyzeCli), action: analyzeTitle })
  }
  const openDiagramPreview = () => {
    if (!mdEditorPath) return
    const norm = mdEditorPath.replace(/\\/g, '/')
    const vars = { FILE: norm, SIDECAR: sidecarPathFor(norm) }
    const prompt = diagramOncePrompt ? resolvePrompt(diagramOncePrompt, vars) : buildDiagramPreviewPrompt(mdEditorPath)
    setPendingRun({ kind: 'diagram', prompt, engine: cliLabel(diagramCli), action: diagramTitle })
  }
  const submitPendingRun = (prompt: string) => {
    const run = pendingRun
    setPendingRun(null)
    if (run?.kind === 'split') void handleSplit(prompt)
    else if (run?.kind === 'analyze') void handleAnalyze(prompt)
    else if (run?.kind === 'diagram') void handleDiagram(prompt)
  }

  // Per-file run state — derived from the store so each open file shows only its own run.
  // A run that completes while the user is on another file updates that file's slot, never this one.
  const splitSlot    = useUiStore(selectMdEditorSplit)
  const analyzeSlot  = useUiStore(selectMdEditorAnalyze)
  const diagramSlot  = useUiStore(selectMdEditorDiagram)
  const splitState   = splitSlot?.status ?? 'idle'
  const analyzeState = analyzeSlot?.status ?? 'idle'
  const diagramState = diagramSlot?.status ?? 'idle'
  const splitStartedAt   = useTerminalStore((s) => s.tabs.find((t) => t.id === splitSlot?.tabId)?.startedAt)
  const analyzeStartedAt = useTerminalStore((s) => s.tabs.find((t) => t.id === analyzeSlot?.tabId)?.startedAt)
  const diagramStartedAt = useTerminalStore((s) => s.tabs.find((t) => t.id === diagramSlot?.tabId)?.startedAt)
  // Elapsed timer is derived from the tab's startedAt so it survives navigation for free.
  const splitProgress   = useElapsedProgress(splitState === 'running' ? splitStartedAt : undefined)
  const analyzeProgress = useElapsedProgress(analyzeState === 'running' ? analyzeStartedAt : undefined)
  const diagramProgress = useElapsedProgress(diagramState === 'running' ? diagramStartedAt : undefined)

  const headerRef = useRef<HTMLDivElement>(null)
  // Responsive collapse tier: 0 = full labels · 1 = AI pills + Visual/Source + Split-cells drop to
  // icons (Save & Export keep labels) · 2 = icon-only everything.
  //
  // Driven by ACTUAL overflow, with HYSTERESIS so it can't flicker icons↔labels while the panel is
  // dragged near the boundary. The trap to avoid: measuring scrollWidth at the CURRENT tier flips
  // the decision every ResizeObserver tick (tier 0 overflows → collapse; tier 1 fits → expand → …).
  // Instead we LEARN the natural fully-labeled width once (measured at tier 0, where the pills +
  // result chips are expanded) and only expand back once there's a clear margin over it — so the
  // decision no longer depends on the current tier.
  const naturalWidthRef = useRef(0)
  const tierRef = useRef(0)
  const [tier, setTier] = useState(0)

  const measureTier = useCallback((): void => {
    const node = headerRef.current
    if (!node) return
    const avail = node.clientWidth
    const cur = tierRef.current
    // Only tier 0 shows every label, so its overflow reveals the true natural width.
    if (cur === 0 && node.scrollWidth > avail + 1) naturalWidthRef.current = node.scrollWidth
    const need = naturalWidthRef.current
    let next = cur
    if (avail < 640) next = 2
    else if (!need || avail >= need + 24) next = 0            // never overflowed, or clear room → labels
    else if (cur === 0 ? node.scrollWidth > avail + 1 : true) next = 1  // collapse on overflow; stay collapsed in the gap
    if (next !== cur) { tierRef.current = next; setTier(next) }
  }, [])

  useEffect(() => {
    const el = headerRef.current
    if (!el) return
    measureTier()
    const obs = new ResizeObserver(() => measureTier())
    obs.observe(el)
    return () => obs.disconnect()
  }, [measureTier])

  // The toolbar's own width changes when result chips appear/disappear, the view toggles, or a
  // preset label length changes — re-learn the natural width from a clean tier-0 state so a stale
  // measurement can't leave it collapsed (or expanded) when the content no longer matches.
  useEffect(() => {
    naturalWidthRef.current = 0
    tierRef.current = 0
    setTier(0)
    const id = requestAnimationFrame(() => measureTier())
    return () => cancelAnimationFrame(id)
  }, [measureTier, mdEditorSplitDraftPath, mdEditorAnalysisPath, mdEditorDiagramPath, viewMode, splitTitle, analyzeTitle, diagramTitle])

  const canUndo = viewMode === 'cells' ? historyIndex > 0            : true
  const canRedo = viewMode === 'cells' ? historyIndex < history.length - 1 : true

  const isCellsDirty = historyIndex !== savedHistoryIndex
  const isSourceDirty = mdEditorPath ? dirtyItems.has(mdEditorPath) : false

  const normPath = mdEditorPath ? mdEditorPath.replace(/\\/g, '/') : ''
  const pathParts = normPath ? normPath.split('/') : []
  const skillName = pathParts[pathParts.length - 1]?.replace('.md', '') ?? ''
  // Only skills/agents can be installed to adapter dirs; the rest of Export applies to any md.
  const isSkillOrAgent = normPath.includes('/skills/') || normPath.includes('/agents/')

  const handleExport = async () => {
    const fragmentOrder = cells
      .filter(c => c.type === 'fragment')
      .map(c => (c as any).fragmentName as string)
    const skillKey = mdEditorPath
      ? mdEditorPath.replace(/\\/g, '/').replace(/^.*core\/skills\//, '').replace('.md', '')
      : 'unknown'
    try {
      const res = await apiFetch('/skills/export', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill: skillKey, fragment_order: fragmentOrder, project_root: useProjectStore.getState().projectPath }),
      })
      if (res.ok) { setExportState('success'); setTimeout(() => setExportState('idle'), 2000) }
      else        { setExportState('error');   setTimeout(() => setExportState('idle'), 3000) }
    } catch      { setExportState('error');    setTimeout(() => setExportState('idle'), 3000) }
  }

  const handleCellsSave = async () => {
    const bodyCells = cells
      .filter(c => c.type === 'body')
      .map(c => ({
        heading: (c as BodyCell).heading,
        headingLevel: (c as BodyCell).headingLevel ?? 2,
        content: (c as BodyCell).content,
      }))
    try {
      const res = await apiFetch('/skills/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_path: mdEditorPath, body_cells: bodyCells, frontmatter: frontmatterRaw }),
      })
      if (res.ok) {
        markCellsSaved()
        setSaveState('success')
        useToastStore.getState().push('Skill saved', 'success', { category: 'db_crud' })
        setTimeout(() => setSaveState('idle'), 2000)
      } else {
        setSaveState('error')
        useToastStore.getState().push('Save failed — server error', 'error', { category: 'db_crud' })
        setTimeout(() => setSaveState('idle'), 3000)
      }
    } catch {
      setSaveState('error')
      useToastStore.getState().push('Save failed — server unreachable', 'error', { category: 'db_crud' })
      setTimeout(() => setSaveState('idle'), 3000)
    }
  }

  const handleUndo = () => { if (viewMode === 'cells') { undo() } else { requestMdEditorUndo() } }
  const handleRedo = () => { if (viewMode === 'cells') { redo() } else { requestMdEditorRedo() } }

  const handleReviewDraft = () => {
    if (viewMode !== 'editor') setMdEditorViewMode('editor')
    requestMdEditorOpenDraft()
  }

  return (
    <div ref={headerRef} className={styles.headerRoot} data-tier={tier}>
      <button
        type="button"
        className={styles.backBtn}
        onClick={() => setMdEditorPath(null)}
        aria-label="Back"
      >
        <ArrowLeft size={16} />
      </button>

      <div className={styles.breadcrumb}>
        <span className={styles.breadcrumbText}>
          <span className={styles.breadcrumbCurrent}>{skillName}</span>
        </span>
      </div>

      <span className={styles.badge}>MD Editor</span>

      {/* View mode toggle */}
      <div className={styles.viewToggle} role="group" aria-label="View mode">
        <Tooltip label="Visual cell editor" placement="bottom">
          <button
            type="button"
            className={styles.viewToggleBtn}
            data-active={viewMode === 'cells'}
            {...(viewMode === 'cells' ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
            onClick={() => viewMode !== 'cells' && onToggleViewMode()}
          >
            <BookOpen size={13} />
            <span className={styles.btnLabel}>Visual</span>
          </button>
        </Tooltip>
        <Tooltip label="Raw source editor" placement="bottom">
          <button
            type="button"
            className={styles.viewToggleBtn}
            data-active={viewMode === 'editor'}
            {...(viewMode === 'editor' ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
            onClick={() => viewMode !== 'editor' && onToggleViewMode()}
          >
            <FileCode size={13} />
            <span className={styles.btnLabel}>Source</span>
          </button>
        </Tooltip>
      </div>

      <div className={styles.spacer} />

      {/* Undo / Redo */}
      <Tooltip
        label={viewMode === 'cells' ? 'Undo' : 'Undo (source editor)'}
        shortcut="Ctrl+Z"
        placement="bottom"
      >
        <button type="button" className={styles.iconBtn} onClick={handleUndo} disabled={!canUndo} aria-label="Undo">
          <Undo2 size={14} />
        </button>
      </Tooltip>
      <Tooltip
        label={viewMode === 'cells' ? 'Redo' : 'Redo (source editor)'}
        shortcut="Ctrl+Shift+Z"
        placement="bottom"
      >
        <button type="button" className={styles.iconBtn} onClick={handleRedo} disabled={!canRedo} aria-label="Redo">
          <Redo2 size={14} />
        </button>
      </Tooltip>

      {/* Deterministic "Split into cells" — standalone; parses structure (no AI, no draft). */}
      <Tooltip label="Split into editable cells — parse structure (no AI)" placement="bottom">
        <button
          type="button"
          className={styles.cellsBtn}
          disabled={!mdEditorPath}
          onClick={() => setSplitCellsOpen(true)}
          aria-label="Split into cells"
        >
          <Scissors size={13} />
          <span className={styles.btnLabel}>Split cells</span>
        </button>
      </Tooltip>

      {/* AI Split — one joined pill: run (title follows preset) │ gear │ Diff result */}
      <ActionPill
        state={splitState === 'success' ? 'done' : splitState}
        progress={splitProgress}
        hasPath={!!mdEditorPath}
        title={splitTitle}
        runningVerb="Splitting"
        mainIcon={<Wand2 size={13} />}
        idleTip={`AI restructures the document — “${splitTitle}” — and delivers a diff you review and accept`}
        runningTip="Reorganizing the document…"
        ariaName="AI Split"
        onRun={openSplitPreview}
        onStop={() => stopSplit()}
        configTip="View or edit the AI Split prompt & preset"
        onToggleConfig={() => setSplitPeekOpen(v => !v)}
        resultIcon={<GitCompare size={12} />}
        resultLabel="Diff"
        resultReady={!!mdEditorSplitDraftPath}
        resultTip={mdEditorSplitDraftPath
          ? 'AI Split draft ready — review the changes'
          : 'No split draft yet — run AI Split to generate one'}
        onOpenResult={handleReviewDraft}
        tone="green"
        compact={tier >= 1}
      />
      {splitPeekOpen && mdEditorPath && (
        <PromptPeekModal
          title="PROMPT — AI Split"
          fileName={skillName + '.md'}
          filePath={mdEditorPath}
          storageKey={STORAGE_KEY_SPLIT}
          presets={SPLIT_PRESETS}
          selectedPreset={splitPreset}
          presetPersistKey={PRESET_KEY_SPLIT}
          cli={splitCli}
          onCliChange={handleSplitCli}
          onClose={() => setSplitPeekOpen(false)}
          onUseOnce={(p) => { setSplitOncePrompt(p); setSplitPeekOpen(false) }}
          onPresetChange={handleSplitPreset}
        />
      )}

      {/* AI Analyze — one joined pill: run (title follows lens) │ gear │ Report result */}
      <ActionPill
        state={analyzeState === 'success' ? 'done' : analyzeState}
        progress={analyzeProgress}
        hasPath={!!mdEditorPath}
        title={analyzeTitle}
        runningVerb="Analyzing"
        mainIcon={<ScanText size={13} />}
        idleTip={`AI will audit “${skillName}” for clarity, gaps, and redundancies — adds a report to the gallery in a side panel`}
        runningTip={`Auditing “${skillName}” for quality issues…`}
        ariaName="AI Analyze"
        onRun={openAnalyzePreview}
        onStop={() => stopAnalyze()}
        configTip="View or edit the prompt sent to the AI engine"
        onToggleConfig={() => setAnalyzePeekOpen(v => !v)}
        resultIcon={<FileSearch size={13} />}
        resultLabel="Reports"
        resultReady={!!mdEditorAnalysisPath}
        resultTip={
          !mdEditorAnalysisPath ? 'No reports yet — run Analyze first'
          : mdEditorAnalysisPanelOpen ? 'Close reports panel'
          : 'Quality reports ready — click to open'
        }
        onOpenResult={() => setMdEditorAnalysisPanelOpen(!mdEditorAnalysisPanelOpen)}
        tone="amber"
        compact={tier >= 1}
      />
      {analyzePeekOpen && mdEditorPath && (
        <PromptPeekModal
          title="PROMPT — AI Analyze"
          fileName={skillName + '.md'}
          filePath={mdEditorPath}
          storageKey={STORAGE_KEY_ANALYZE}
          presets={ANALYZE_LENSES}
          selectedPreset={analyzePreset}
          presetPersistKey={PRESET_KEY_ANALYZE}
          cli={analyzeCli}
          onCliChange={handleAnalyzeCli}
          onClose={() => setAnalyzePeekOpen(false)}
          onUseOnce={(p) => { setAnalyzeOncePrompt(p); setAnalyzePeekOpen(false) }}
          onPresetChange={handleAnalyzePreset}
        />
      )}

      {/* Diagram — one joined pill: run (title follows preset) │ gear │ Gallery result */}
      <ActionPill
        state={diagramState === 'success' ? 'done' : diagramState}
        progress={diagramProgress}
        hasPath={!!mdEditorPath}
        title={diagramTitle}
        runningVerb="Diagramming"
        mainIcon={<Network size={13} />}
        idleTip={`AI generates a visual diagram of “${skillName}” — opens a gallery of cards you can view full-screen`}
        runningTip={`Generating a diagram of “${skillName}”…`}
        ariaName="Diagram"
        onRun={openDiagramPreview}
        onStop={() => stopDiagram()}
        configTip="Pick a diagram style or edit the prompt"
        onToggleConfig={() => setDiagramPeekOpen(v => !v)}
        resultIcon={<ImageIcon size={13} />}
        resultLabel="Gallery"
        resultReady={!!mdEditorDiagramPath}
        resultTip={
          !mdEditorDiagramPath ? 'No diagrams yet — run Diagram first'
          : mdEditorDiagramPanelOpen ? 'Close diagram gallery'
          : 'Diagrams ready — click to open the gallery'
        }
        onOpenResult={() => setMdEditorDiagramPanelOpen(!mdEditorDiagramPanelOpen)}
        tone="green"
        compact={tier >= 1}
      />
      {diagramPeekOpen && mdEditorPath && (
        <PromptPeekModal
          title="PROMPT — Diagram"
          fileName={skillName + '.md'}
          filePath={mdEditorPath}
          storageKey={STORAGE_KEY_DIAGRAM}
          presets={DIAGRAM_PRESETS}
          selectedPreset={diagramPreset}
          presetPersistKey={PRESET_KEY_DIAGRAM}
          cli={diagramCli}
          onCliChange={handleDiagramCli}
          onClose={() => setDiagramPeekOpen(false)}
          onUseOnce={(p) => { setDiagramOncePrompt(p); setDiagramPeekOpen(false) }}
          onPresetChange={handleDiagramPreset}
        />
      )}

      {/* Save — both modes, different handlers */}
      {viewMode === 'cells' ? (
        <Tooltip label="Save" shortcut="Ctrl+S" placement="bottom">
          <button
            type="button"
            className={styles.saveBtn}
            data-state={isCellsDirty ? saveState : (saveState === 'success' ? 'success' : 'saved')}
            onClick={isCellsDirty ? handleCellsSave : undefined}
            disabled={!isCellsDirty && saveState === 'idle'}
          >
            <Database size={14} />
            <span className={styles.btnLabel}>
              {saveState === 'error' ? 'Error' : isCellsDirty ? 'Save' : 'Saved'}
            </span>
          </button>
        </Tooltip>
      ) : (
        <Tooltip label="Save file" shortcut="Ctrl+S" placement="bottom">
          <button
            type="button"
            className={styles.saveBtn}
            data-state={isSourceDirty ? 'idle' : 'saved'}
            onClick={requestMdEditorSave}
            disabled={!isSourceDirty}
          >
            <Database size={14} />
            <span className={styles.btnLabel}>
              {isSourceDirty ? 'Save' : 'Saved'}
            </span>
          </button>
        </Tooltip>
      )}

      {/* Export ▾ — far right. Save-as / Download / Copy for any md; Install for skills. */}
      <ExportMenu
        path={mdEditorPath}
        isSkillOrAgent={isSkillOrAgent}
        installState={exportState}
        onInstallSkill={handleExport}
        compact={tier >= 2}
      />

      {/* Deterministic "Split into cells" — parses the open file into editable cells. */}
      {splitCellsOpen && mdEditorPath && (
        <SkillSplitModal
          filePath={mdEditorPath}
          fileName={skillName + '.md'}
          onClose={() => setSplitCellsOpen(false)}
          onInsertOne={(raw) => {
            setSplitCellsOpen(false)
            if (viewMode !== 'cells') setMdEditorViewMode('cells')
            const lastId = cells[cells.length - 1]?.id ?? null
            insertBodyCell(skillName, raw, lastId)
          }}
          onConfirm={(proposed) => {
            setSplitCellsOpen(false)
            if (viewMode !== 'cells') setMdEditorViewMode('cells')
            let lastId = cells[cells.length - 1]?.id ?? null
            for (const c of proposed) lastId = insertBodyCell(c.heading, c.content, lastId)
          }}
        />
      )}

      {/* Confirm-before-send preview for AI Split / AI Analyze / Diagram. */}
      {pendingRun && (
        <SendPreviewModal
          title={pendingRun.action}
          engineLabel={pendingRun.engine}
          fileName={skillName + '.md'}
          prompt={pendingRun.prompt}
          submitLabel={
            pendingRun.kind === 'split' ? 'Run Split'
            : pendingRun.kind === 'analyze' ? 'Run Analyze'
            : 'Run Diagram'
          }
          onSubmit={submitPendingRun}
          onCancel={() => setPendingRun(null)}
        />
      )}
    </div>
  )
}
