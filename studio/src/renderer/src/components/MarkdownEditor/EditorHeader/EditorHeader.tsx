import React, { useState, useRef, useEffect } from 'react'
import { useToastStore } from '../../../store/toastStore'
import {
  ArrowLeft, Undo2, Redo2, Database, FileCode, BookOpen, GitCompare,
  ScanText, FileSearch, SlidersHorizontal, Square,
} from 'lucide-react'
import { Tooltip } from '../../ui'
import { useMarkdownEditorStore, BodyCell } from '../../../store/markdownEditorStore'
import { useUiStore, selectMdEditorDraftPath, selectMdEditorAnalysisPath, selectMdEditorSplit, selectMdEditorAnalyze } from '../../../store/uiStore'
import { useTerminalStore } from '../../../store/terminalStore'
import { useEditorAgentActions } from './hooks/useEditorAgentActions'
import { apiFetch } from '../../../lib/config'
import { STORAGE_KEY_SPLIT, STORAGE_KEY_ANALYZE } from '../../Editor/commentUtils'
import PromptPeekModal from './PromptPeekModal/PromptPeekModal'
import ExportMenu from './ExportMenu/ExportMenu'
import SplitPill from './SplitPill/SplitPill'
import { loadEditorCli, saveEditorCli, EditorCli, CLI_KEY_SPLIT, CLI_KEY_ANALYZE, loadPreset, savePreset, PRESET_KEY_SPLIT, PRESET_KEY_ANALYZE } from './editorCli'
import { SPLIT_PRESETS, ANALYZE_LENSES } from './actionPresets'
import { fmtElapsed, useElapsedProgress } from './editorProgress'
import SkillSplitModal from '../../shared/SkillSplitModal/SkillSplitModal'
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
  const mdEditorDraftPath         = useUiStore(selectMdEditorDraftPath)
  const requestMdEditorSave       = useUiStore(s => s.requestMdEditorSave)
  const requestMdEditorOpenDraft  = useUiStore(s => s.requestMdEditorOpenDraft)
  const requestMdEditorUndo       = useUiStore(s => s.requestMdEditorUndo)
  const requestMdEditorRedo       = useUiStore(s => s.requestMdEditorRedo)
  const mdEditorAnalysisPath       = useUiStore(selectMdEditorAnalysisPath)
  const mdEditorAnalysisPanelOpen  = useUiStore(s => s.mdEditorAnalysisPanelOpen)
  const setMdEditorAnalysisPanelOpen = useUiStore(s => s.setMdEditorAnalysisPanelOpen)

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

  const handleSplitCli   = (next: EditorCli) => { setSplitCli(next);   saveEditorCli(CLI_KEY_SPLIT, next) }
  const handleAnalyzeCli = (next: EditorCli) => { setAnalyzeCli(next); saveEditorCli(CLI_KEY_ANALYZE, next) }

  const handleSplitPreset = (name: string) => { setSplitPreset(name); savePreset(PRESET_KEY_SPLIT, name) }
  const handleAnalyzePreset = (name: string) => { setAnalyzePreset(name); savePreset(PRESET_KEY_ANALYZE, name) }

  const { handleSplit, handleAnalyze, stopSplit, stopAnalyze } = useEditorAgentActions(
    mdEditorPath,
    splitOncePrompt,
    analyzeOncePrompt,
    () => setSplitOncePrompt(null),
    () => setAnalyzeOncePrompt(null),
    splitCli,
    analyzeCli,
  )

  // Per-file run state — derived from the store so each open file shows only its own run.
  // A run that completes while the user is on another file updates that file's slot, never this one.
  const splitSlot    = useUiStore(selectMdEditorSplit)
  const analyzeSlot  = useUiStore(selectMdEditorAnalyze)
  const splitState   = splitSlot?.status ?? 'idle'
  const analyzeState = analyzeSlot?.status ?? 'idle'
  const splitStartedAt   = useTerminalStore((s) => s.tabs.find((t) => t.id === splitSlot?.tabId)?.startedAt)
  const analyzeStartedAt = useTerminalStore((s) => s.tabs.find((t) => t.id === analyzeSlot?.tabId)?.startedAt)
  // Elapsed timer is derived from the tab's startedAt so it survives navigation for free.
  const splitProgress   = useElapsedProgress(splitState === 'running' ? splitStartedAt : undefined)
  const analyzeProgress = useElapsedProgress(analyzeState === 'running' ? analyzeStartedAt : undefined)

  const headerRef = useRef<HTMLDivElement>(null)
  const [isCompact, setIsCompact] = useState(false)

  useEffect(() => {
    const el = headerRef.current
    if (!el) return
    const obs = new ResizeObserver(entries => {
      setIsCompact(entries[0].contentRect.width < 760)
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

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
        body: JSON.stringify({ skill: skillKey, fragment_order: fragmentOrder }),
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
    <div ref={headerRef} className={styles.headerRoot} data-compact={isCompact}>
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
            aria-pressed={viewMode === 'cells'}
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
            aria-pressed={viewMode === 'editor'}
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

      {/* Split — split-button: AI Split (primary) + caret menu (AI vs deterministic) + prompt gear */}
      <SplitPill
        state={splitState}
        progress={splitProgress}
        hasPath={!!mdEditorPath}
        onAiSplit={() => void handleSplit()}
        onStop={() => stopSplit()}
        onSplitIntoCells={() => setSplitCellsOpen(true)}
        onTogglePrompt={() => setSplitPeekOpen(v => !v)}
        compact={isCompact}
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

      {/* Analyze pill */}
      <div className={styles.agentPill}>
        <Tooltip
          label={analyzeState === 'running'
            ? (analyzeProgress?.detail || `Auditing "${skillName}" for quality issues…`)
            : `AI will audit "${skillName}" for clarity, gaps, and redundancies — opens a quality report in a side panel`}
          placement="bottom"
        >
          <button
            type="button"
            className={styles.agentPillMain}
            data-state={analyzeState}
            disabled={analyzeState === 'running' || !mdEditorPath}
            onClick={() => void handleAnalyze()}
            aria-label="AI Analyze document for quality"
          >
            <ScanText size={13} />
            <span className={styles.btnLabel}>
              {analyzeState === 'running'
                ? (analyzeProgress ? `Analyzing… ${fmtElapsed(analyzeProgress.elapsedS)}` : 'Analyzing…')
                : analyzeState === 'success' ? 'Done' : analyzeState === 'error' ? 'Error' : 'AI Analyze'}
            </span>
          </button>
        </Tooltip>
        {analyzeState === 'running' ? (
          <Tooltip label="Stop the running engine" placement="bottom">
            <button
              type="button"
              className={styles.agentPillStop}
              onClick={() => stopAnalyze()}
              aria-label="Stop analyze"
            >
              <Square size={11} />
            </button>
          </Tooltip>
        ) : (
          <Tooltip label="View or edit the prompt sent to the AI engine" placement="bottom">
            <button
              type="button"
              className={styles.agentPillSettings}
              data-state={analyzeState}
              disabled={!mdEditorPath}
              onClick={() => setAnalyzePeekOpen(v => !v)}
              aria-label="Edit analyze prompt"
            >
              <SlidersHorizontal size={11} />
            </button>
          </Tooltip>
        )}
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
      </div>

      {/* View Analysis Report */}
      <Tooltip
        label={
          !mdEditorAnalysisPath ? 'No report yet — run Analyze first' :
          mdEditorAnalysisPanelOpen ? 'Close report panel' :
          'Quality report ready — click to open'
        }
        placement="bottom"
      >
        <button
          type="button"
          className={styles.analysisBtn}
          data-has-analysis={!!mdEditorAnalysisPath}
          aria-disabled={!mdEditorAnalysisPath}
          onClick={mdEditorAnalysisPath ? () => setMdEditorAnalysisPanelOpen(!mdEditorAnalysisPanelOpen) : undefined}
        >
          <FileSearch size={13} />
          <span className={styles.btnLabel}>Report</span>
        </button>
      </Tooltip>

      {/* Review Draft */}
      <Tooltip
        label={mdEditorDraftPath
          ? 'Agent draft ready — click to review changes'
          : 'No agent draft pending — activates when an agent edits this file'}
        placement="bottom"
      >
        <button
          type="button"
          className={styles.draftBtn}
          data-has-draft={!!mdEditorDraftPath}
          aria-disabled={!mdEditorDraftPath}
          onClick={mdEditorDraftPath ? handleReviewDraft : undefined}
        >
          <GitCompare size={13} />
          <span className={styles.btnLabel}>Review draft</span>
        </button>
      </Tooltip>

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
        compact={isCompact}
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
    </div>
  )
}
