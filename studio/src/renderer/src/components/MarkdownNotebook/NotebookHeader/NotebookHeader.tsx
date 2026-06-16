import React, { useState, useRef, useEffect } from 'react'
import { useToastStore } from '../../../store/toastStore'
import {
  ArrowLeft, Undo2, Redo2, Database, FileCode, BookOpen, GitCompare,
  ScanText, FileSearch, SlidersHorizontal,
} from 'lucide-react'
import { Tooltip } from '../../ui'
import { useNotebookStore, BodyCell } from '../../../store/notebookStore'
import { useUiStore } from '../../../store/uiStore'
import { useNotebookAgentActions } from './hooks/useNotebookAgentActions'
import { apiFetch } from '../../../lib/config'
import { buildSplitPrompt, buildAnalyzePrompt, STORAGE_KEY_SPLIT, STORAGE_KEY_ANALYZE } from '../../Editor/commentUtils'
import PromptPeekModal from './PromptPeekModal/PromptPeekModal'
import ExportMenu from './ExportMenu/ExportMenu'
import SplitPill from './SplitPill/SplitPill'
import SkillSplitModal from '../../shared/SkillSplitModal/SkillSplitModal'
import styles from './NotebookHeader.module.css'

export type NotebookViewMode = 'cells' | 'editor'

interface Props {
  viewMode: NotebookViewMode
  onToggleViewMode: () => void
}

export default function NotebookHeader({ viewMode, onToggleViewMode }: Props) {
  const { undo, redo, cells, historyIndex, savedHistoryIndex, history, markCellsSaved, insertBodyCell, frontmatterRaw } = useNotebookStore()

  const notebookPath         = useUiStore(s => s.notebookPath)
  const setNotebookPath      = useUiStore(s => s.setNotebookPath)
  const setNotebookViewMode  = useUiStore(s => s.setNotebookViewMode)
  const dirtyItems                = useUiStore(s => s.dirtyItems)
  const notebookDraftPath         = useUiStore(s => s.notebookDraftPath)
  const requestNotebookSave       = useUiStore(s => s.requestNotebookSave)
  const requestNotebookOpenDraft  = useUiStore(s => s.requestNotebookOpenDraft)
  const requestNotebookUndo       = useUiStore(s => s.requestNotebookUndo)
  const requestNotebookRedo       = useUiStore(s => s.requestNotebookRedo)
  const notebookAnalysisPath       = useUiStore(s => s.notebookAnalysisPath)
  const notebookAnalysisPanelOpen  = useUiStore(s => s.notebookAnalysisPanelOpen)
  const setNotebookAnalysisPanelOpen = useUiStore(s => s.setNotebookAnalysisPanelOpen)

  const [exportState, setExportState] = useState<'idle' | 'success' | 'error'>('idle')
  const [saveState,   setSaveState]   = useState<'idle' | 'success' | 'error'>('idle')
  const [splitPeekOpen,    setSplitPeekOpen]    = useState(false)
  const [splitCellsOpen,   setSplitCellsOpen]   = useState(false)
  const [analyzePeekOpen,  setAnalyzePeekOpen]  = useState(false)
  const [splitOncePrompt,  setSplitOncePrompt]  = useState<string | null>(null)
  const [analyzeOncePrompt, setAnalyzeOncePrompt] = useState<string | null>(null)

  const { handleSplit, handleAnalyze, splitState, analyzeState } = useNotebookAgentActions(
    notebookPath,
    splitOncePrompt,
    analyzeOncePrompt,
    () => setSplitOncePrompt(null),
    () => setAnalyzeOncePrompt(null),
  )

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
  const isSourceDirty = notebookPath ? dirtyItems.has(notebookPath) : false

  const normPath = notebookPath ? notebookPath.replace(/\\/g, '/') : ''
  const pathParts = normPath ? normPath.split('/') : []
  const skillName = pathParts[pathParts.length - 1]?.replace('.md', '') ?? ''
  // Only skills/agents can be installed to adapter dirs; the rest of Export applies to any md.
  const isSkillOrAgent = normPath.includes('/skills/') || normPath.includes('/agents/')

  const handleExport = async () => {
    const fragmentOrder = cells
      .filter(c => c.type === 'fragment')
      .map(c => (c as any).fragmentName as string)
    const skillKey = notebookPath
      ? notebookPath.replace(/\\/g, '/').replace(/^.*core\/skills\//, '').replace('.md', '')
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
        body: JSON.stringify({ skill_path: notebookPath, body_cells: bodyCells, frontmatter: frontmatterRaw }),
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

  const handleUndo = () => { if (viewMode === 'cells') { undo() } else { requestNotebookUndo() } }
  const handleRedo = () => { if (viewMode === 'cells') { redo() } else { requestNotebookRedo() } }

  const handleReviewDraft = () => {
    if (viewMode !== 'editor') setNotebookViewMode('editor')
    requestNotebookOpenDraft()
  }

  return (
    <div ref={headerRef} className={styles.headerRoot} data-compact={isCompact}>
      <button
        type="button"
        className={styles.backBtn}
        onClick={() => setNotebookPath(null)}
        aria-label="Back"
      >
        <ArrowLeft size={16} />
      </button>

      <div className={styles.breadcrumb}>
        <span className={styles.breadcrumbText}>
          <span className={styles.breadcrumbCurrent}>{skillName}</span>
        </span>
      </div>

      <span className={styles.badge}>NOTEBOOK</span>

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
        hasPath={!!notebookPath}
        onAiSplit={() => void handleSplit()}
        onSplitIntoCells={() => setSplitCellsOpen(true)}
        onTogglePrompt={() => setSplitPeekOpen(v => !v)}
        compact={isCompact}
      />
      {splitPeekOpen && notebookPath && (
        <PromptPeekModal
          title="PROMPT — AI Split"
          fileName={skillName + '.md'}
          defaultPrompt={buildSplitPrompt(notebookPath)}
          storageKey={STORAGE_KEY_SPLIT}
          onClose={() => setSplitPeekOpen(false)}
          onUseOnce={(p) => { setSplitOncePrompt(p); setSplitPeekOpen(false) }}
        />
      )}

      {/* Analyze pill */}
      <div className={styles.agentPill}>
        <Tooltip
          label={analyzeState === 'running'
            ? `Auditing "${skillName}" for quality issues…`
            : `AI will audit "${skillName}" for clarity, gaps, and redundancies — opens a quality report in a side panel`}
          placement="bottom"
        >
          <button
            type="button"
            className={styles.agentPillMain}
            data-state={analyzeState}
            disabled={analyzeState === 'running' || !notebookPath}
            onClick={() => void handleAnalyze()}
            aria-label="AI Analyze document for quality"
          >
            <ScanText size={13} />
            <span className={styles.btnLabel}>
              {analyzeState === 'running' ? 'Analyzing…' : analyzeState === 'success' ? 'Done' : analyzeState === 'error' ? 'Error' : 'AI Analyze'}
            </span>
          </button>
        </Tooltip>
        <Tooltip label="View or edit the prompt sent to Claude" placement="bottom">
          <button
            type="button"
            className={styles.agentPillSettings}
            data-state={analyzeState}
            disabled={!notebookPath}
            onClick={() => setAnalyzePeekOpen(v => !v)}
            aria-label="Edit analyze prompt"
          >
            <SlidersHorizontal size={11} />
          </button>
        </Tooltip>
        {analyzePeekOpen && notebookPath && (
          <PromptPeekModal
            title="PROMPT — AI Analyze"
            fileName={skillName + '.md'}
            defaultPrompt={buildAnalyzePrompt(notebookPath)}
            storageKey={STORAGE_KEY_ANALYZE}
            onClose={() => setAnalyzePeekOpen(false)}
            onUseOnce={(p) => { setAnalyzeOncePrompt(p); setAnalyzePeekOpen(false) }}
          />
        )}
      </div>

      {/* View Analysis Report */}
      <Tooltip
        label={
          !notebookAnalysisPath ? 'No report yet — run Analyze first' :
          notebookAnalysisPanelOpen ? 'Close report panel' :
          'Quality report ready — click to open'
        }
        placement="bottom"
      >
        <button
          type="button"
          className={styles.analysisBtn}
          data-has-analysis={!!notebookAnalysisPath}
          aria-disabled={!notebookAnalysisPath}
          onClick={notebookAnalysisPath ? () => setNotebookAnalysisPanelOpen(!notebookAnalysisPanelOpen) : undefined}
        >
          <FileSearch size={13} />
          <span className={styles.btnLabel}>Report</span>
        </button>
      </Tooltip>

      {/* Review Draft */}
      <Tooltip
        label={notebookDraftPath
          ? 'Agent draft ready — click to review changes'
          : 'No agent draft pending — activates when an agent edits this file'}
        placement="bottom"
      >
        <button
          type="button"
          className={styles.draftBtn}
          data-has-draft={!!notebookDraftPath}
          aria-disabled={!notebookDraftPath}
          onClick={notebookDraftPath ? handleReviewDraft : undefined}
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
            onClick={requestNotebookSave}
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
        path={notebookPath}
        isSkillOrAgent={isSkillOrAgent}
        installState={exportState}
        onInstallSkill={handleExport}
        compact={isCompact}
      />

      {/* Deterministic "Split into cells" — parses the open file into editable cells. */}
      {splitCellsOpen && notebookPath && (
        <SkillSplitModal
          filePath={notebookPath}
          fileName={skillName + '.md'}
          onClose={() => setSplitCellsOpen(false)}
          onInsertOne={(raw) => {
            setSplitCellsOpen(false)
            if (viewMode !== 'cells') setNotebookViewMode('cells')
            const lastId = cells[cells.length - 1]?.id ?? null
            insertBodyCell(skillName, raw, lastId)
          }}
          onConfirm={(proposed) => {
            setSplitCellsOpen(false)
            if (viewMode !== 'cells') setNotebookViewMode('cells')
            let lastId = cells[cells.length - 1]?.id ?? null
            for (const c of proposed) lastId = insertBodyCell(c.heading, c.content, lastId)
          }}
        />
      )}
    </div>
  )
}
