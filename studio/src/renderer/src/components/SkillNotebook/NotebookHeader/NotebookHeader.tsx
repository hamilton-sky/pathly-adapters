import React, { useState } from 'react'
import { useToastStore } from '../../../store/toastStore'
import {
  ArrowLeft, Undo2, Redo2, Database, Download, FileCode, BookOpen, GitCompare,
  Scissors, ScanText,
} from 'lucide-react'
import { Tooltip } from '../../ui'
import { useSkillNotebookStore, BodyCell } from '../../../store/skillNotebookStore'
import { useUiStore } from '../../../store/uiStore'
import { useNotebookAgentActions } from './hooks/useNotebookAgentActions'
import styles from './NotebookHeader.module.css'

export type NotebookViewMode = 'cells' | 'editor'

interface Props {
  viewMode: NotebookViewMode
  onToggleViewMode: () => void
}

export default function NotebookHeader({ viewMode, onToggleViewMode }: Props) {
  const { undo, redo, cells, historyIndex, savedHistoryIndex, history, markCellsSaved } = useSkillNotebookStore()

  const skillNotebookPath         = useUiStore(s => s.skillNotebookPath)
  const setSkillNotebookPath      = useUiStore(s => s.setSkillNotebookPath)
  const setSkillNotebookViewMode  = useUiStore(s => s.setSkillNotebookViewMode)
  const dirtyItems                = useUiStore(s => s.dirtyItems)
  const notebookDraftPath         = useUiStore(s => s.notebookDraftPath)
  const requestNotebookSave       = useUiStore(s => s.requestNotebookSave)
  const requestNotebookOpenDraft  = useUiStore(s => s.requestNotebookOpenDraft)
  const requestNotebookUndo       = useUiStore(s => s.requestNotebookUndo)
  const requestNotebookRedo       = useUiStore(s => s.requestNotebookRedo)

  const { handleSplit, handleAnalyze, splitState, analyzeState } = useNotebookAgentActions(skillNotebookPath)

  const [exportState, setExportState] = useState<'idle' | 'success' | 'error'>('idle')
  const [saveState,   setSaveState]   = useState<'idle' | 'success' | 'error'>('idle')

  // Cells mode: history-depth gating; Source mode: always allow (CodeMirror will no-op if empty)
  const canUndo = viewMode === 'cells' ? historyIndex > 0            : true
  const canRedo = viewMode === 'cells' ? historyIndex < history.length - 1 : true

  // Visual mode: dirty when cells have changed since the last save (or load)
  const isCellsDirty = historyIndex !== savedHistoryIndex
  // Source mode: dirty when the raw text has been edited
  const isSourceDirty = skillNotebookPath ? dirtyItems.has(skillNotebookPath) : false

  const pathParts = skillNotebookPath ? skillNotebookPath.replace(/\\/g, '/').split('/') : []
  const skillName = pathParts[pathParts.length - 1]?.replace('.md', '') ?? ''
  const category  = pathParts[pathParts.length - 2] ?? ''

  // ── Export (same for both modes) ──────────────────────────────────────────
  const handleExport = async () => {
    const fragmentOrder = cells
      .filter(c => c.type === 'fragment')
      .map(c => (c as any).fragmentName as string)
    const skillKey = skillNotebookPath
      ? skillNotebookPath.replace(/\\/g, '/').replace(/^.*core\/skills\//, '').replace('.md', '')
      : 'unknown'
    try {
      const res = await fetch('http://localhost:8765/skills/export', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill: skillKey, fragment_order: fragmentOrder }),
      })
      if (res.ok) { setExportState('success'); setTimeout(() => setExportState('idle'), 2000) }
      else        { setExportState('error');   setTimeout(() => setExportState('idle'), 3000) }
    } catch      { setExportState('error');    setTimeout(() => setExportState('idle'), 3000) }
  }

  // ── Save — cells mode: POST cells to FSM; source mode: signal embedded Editor
  const handleCellsSave = async () => {
    const bodyCells = cells
      .filter(c => c.type === 'body')
      .map(c => ({ heading: (c as BodyCell).heading, content: (c as BodyCell).content }))
    try {
      const res = await fetch('http://localhost:8765/skills/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_path: skillNotebookPath, body_cells: bodyCells }),
      })
      if (res.ok) {
        markCellsSaved()                    // record this historyIndex as the new clean baseline
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

  // ── Undo / Redo — routes to cell store (Visual) or CodeMirror (Source) ─────
  const handleUndo = () => { if (viewMode === 'cells') { undo() } else { requestNotebookUndo() } }
  const handleRedo = () => { if (viewMode === 'cells') { redo() } else { requestNotebookRedo() } }

  // ── Review Draft — switch to source if needed, then open the diff viewer ──
  const handleReviewDraft = () => {
    if (viewMode !== 'editor') setSkillNotebookViewMode('editor')
    requestNotebookOpenDraft()
  }

  return (
    <div className={styles.headerRoot}>
      <button
        type="button"
        className={styles.backBtn}
        onClick={() => setSkillNotebookPath(null)}
        aria-label="Back"
      >
        <ArrowLeft size={16} />
      </button>

      <div className={styles.breadcrumb}>
        <span className={styles.breadcrumbText}>
          Skills › {category} › <span className={styles.breadcrumbCurrent}>{skillName}</span>
        </span>
      </div>

      <span className={styles.badge}>NOTEBOOK</span>

      <div className={styles.spacer} />

      {/* Undo / Redo — both modes; cells = cell history, source = CodeMirror history */}
      <Tooltip
        label={viewMode === 'cells' ? 'Undo' : 'Undo (source editor)'}
        shortcut="Ctrl+Z"
        placement="bottom"
      >
        <button type="button" className={styles.iconBtn} onClick={handleUndo} disabled={!canUndo} aria-label="Undo">
          <Undo2 size={15} />
        </button>
      </Tooltip>
      <Tooltip
        label={viewMode === 'cells' ? 'Redo' : 'Redo (source editor)'}
        shortcut="Ctrl+Shift+Z"
        placement="bottom"
      >
        <button type="button" className={styles.iconBtn} onClick={handleRedo} disabled={!canRedo} aria-label="Redo">
          <Redo2 size={15} />
        </button>
      </Tooltip>

      {/* Split — agent restructures cells; produces a .draft for diff review */}
      <Tooltip
        label={splitState === 'running'
          ? 'Agent is splitting the skill…'
          : 'Ask an agent to split this skill into well-organized sections (produces a reviewable draft)'}
        placement="bottom"
      >
        <button
          type="button"
          className={styles.agentBtn}
          data-state={splitState}
          disabled={splitState === 'running' || !skillNotebookPath}
          onClick={() => void handleSplit()}
          aria-label="Split skill into sections"
        >
          <Scissors size={14} />
          {splitState === 'running' ? 'Splitting…' : splitState === 'success' ? 'Split!' : splitState === 'error' ? 'Error' : 'Split'}
        </button>
      </Tooltip>

      {/* Analyze — agent writes a quality report to .analysis */}
      <Tooltip
        label={analyzeState === 'running'
          ? 'Agent is analyzing the skill…'
          : 'Ask an agent to analyze this skill for clarity, gaps, and improvements'}
        placement="bottom"
      >
        <button
          type="button"
          className={styles.agentBtn}
          data-state={analyzeState}
          disabled={analyzeState === 'running' || !skillNotebookPath}
          onClick={() => void handleAnalyze()}
          aria-label="Analyze skill"
        >
          <ScanText size={14} />
          {analyzeState === 'running' ? 'Analyzing…' : analyzeState === 'success' ? 'Done' : analyzeState === 'error' ? 'Error' : 'Analyze'}
        </button>
      </Tooltip>

      {/* Review Draft — always visible; disabled until an agent draft exists */}
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
          <GitCompare size={14} />
          Review draft
        </button>
      </Tooltip>

      {/* Save — both modes, different handlers, identical appearance logic */}
      {viewMode === 'cells' ? (
        <Tooltip label="Save skill" shortcut="Ctrl+S" placement="bottom">
          <button
            type="button"
            className={styles.saveBtn}
            data-state={isCellsDirty ? saveState : (saveState === 'success' ? 'success' : 'saved')}
            onClick={isCellsDirty ? handleCellsSave : undefined}
            disabled={!isCellsDirty && saveState === 'idle'}
          >
            <Database size={15} />
            {saveState === 'error' ? 'Error' : isCellsDirty ? 'Save' : 'Saved'}
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
            <Database size={15} />
            {isSourceDirty ? 'Save' : 'Saved'}
          </button>
        </Tooltip>
      )}

      {/* Export Skill — both modes */}
      <button
        type="button"
        className={styles.exportBtn}
        data-state={exportState}
        onClick={handleExport}
        disabled={exportState !== 'idle'}
      >
        <Download size={15} />
        {exportState === 'success' ? 'Exported' : exportState === 'error' ? 'Error' : 'Export Skill'}
      </button>

      {/* View mode toggle — Visual (cells) ↔ Source (raw editor) */}
      <div className={styles.viewToggle} role="group" aria-label="View mode">
        <Tooltip label="Visual cell editor" placement="bottom">
          <button
            type="button"
            className={styles.viewToggleBtn}
            data-active={viewMode === 'cells'}
            aria-pressed={viewMode === 'cells'}
            onClick={() => viewMode !== 'cells' && onToggleViewMode()}
          >
            <BookOpen size={14} />
            <span>Visual</span>
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
            <FileCode size={14} />
            <span>Source</span>
          </button>
        </Tooltip>
      </div>
    </div>
  )
}
