// Right-docked gallery panel (mirrors DiagramGalleryPanel): lists the file's analysis
// report cards, newest first; each card expands to its rendered markdown. The header is one
// ActionPill — New (run the selected lens) │ gear (PromptPeekModal config) │ elapsed timer +
// stop while a run is in flight. Generation lives in useAnalysisGeneration.

import React, { useEffect } from 'react'
import { X, Sparkles, FileSearch } from 'lucide-react'
import {
  useUiStore,
  selectMdEditorAnalysisPath,
  selectMdEditorAnalyze,
} from '../../../store/uiStore'
import { useTerminalStore } from '../../../store/terminalStore'
import { useAnalysisSidecar } from './useAnalysisSidecar'
import { useAnalysisGeneration } from './useAnalysisGeneration'
import { useElapsedProgress } from '../EditorHeader/editorProgress'
import { ANALYZE_LENSES } from '../EditorHeader/actionPresets'
import { PRESET_KEY_ANALYZE } from '../EditorHeader/editorCli'
import { STORAGE_KEY_ANALYZE } from '../../Editor/commentUtils'
import PromptPeekModal from '../EditorHeader/PromptPeekModal/PromptPeekModal'
import ActionPill from '../../shared/ActionPill/ActionPill'
import AnalysisCard from './AnalysisCard/AnalysisCard'
import styles from './AnalysisGalleryPanel.module.css'

export default function AnalysisGalleryPanel() {
  const mdEditorPath = useUiStore((s) => s.mdEditorPath)
  const analysisPath = useUiStore(selectMdEditorAnalysisPath)
  const panelOpen = useUiStore((s) => s.mdEditorAnalysisPanelOpen)
  const setPanelOpen = useUiStore((s) => s.setMdEditorAnalysisPanelOpen)
  const slot = useUiStore(selectMdEditorAnalyze)
  const startedAt = useTerminalStore((s) => s.tabs.find((t) => t.id === slot?.tabId)?.startedAt)

  const { analyses, loading, reload, remove } = useAnalysisSidecar(mdEditorPath)
  const gen = useAnalysisGeneration(mdEditorPath)

  const analyzeState = slot?.status ?? 'idle'
  const isBusy = analyzeState === 'running'
  const progress = useElapsedProgress(analyzeState === 'running' ? startedAt : undefined)

  // Refresh the cards when a run completes (file path unchanged → the sidecar hook's own
  // effect won't re-fire; watch the slot transition instead).
  useEffect(() => {
    if (slot?.status === 'success') reload()
  }, [slot?.status, reload])

  if (!analysisPath || !panelOpen) return null

  const fileName = (mdEditorPath ?? '').replace(/\\/g, '/').split('/').pop() ?? 'file'
  const handleNew = () => gen.fromLens(gen.localPreset)
  // Newest first; the freshest report opens expanded.
  const ordered = [...analyses].reverse()

  async function handleDelete(id: string) {
    const remaining = await remove(id)
    if (remaining === 0) setPanelOpen(false)
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.title}>
          Reports
          {analyses.length > 0 && <span className={styles.count}>{analyses.length}</span>}
        </span>
        <ActionPill
          state={analyzeState === 'success' ? 'done' : analyzeState}
          progress={progress}
          hasPath={!!mdEditorPath}
          title="New"
          runningVerb="Analyzing"
          mainIcon={<Sparkles size={13} />}
          idleTip="Run the selected lens to add a new report"
          runningTip="Analyzing…"
          ariaName="Analyze"
          onRun={handleNew}
          onStop={() => gen.stopAnalyze()}
          configTip="Lens / prompt / engine"
          onToggleConfig={() => gen.setPeekOpen(true)}
        />
        <button
          type="button"
          className={styles.closeBtn}
          onClick={() => setPanelOpen(false)}
          aria-label="Close reports"
        >
          <X size={14} />
        </button>
      </div>

      <div className={styles.body}>
        {loading && analyses.length === 0 ? (
          <div className={styles.empty}>Loading…</div>
        ) : analyses.length === 0 ? (
          <div className={styles.empty}>
            <FileSearch size={22} />
            <span>No reports yet.</span>
            <button type="button" className={styles.emptyCta} onClick={handleNew} disabled={isBusy || !mdEditorPath}>
              Run analysis
            </button>
          </div>
        ) : (
          <div className={styles.list}>
            {ordered.map((a, i) => (
              <AnalysisCard
                key={a.id}
                entry={a}
                defaultExpanded={i === 0}
                targets={gen.boardTargets}
                onAddToBoard={(e, t) => void gen.addToBoard(e, t).then((ok) => ok && reload())}
                onDelete={(e) => void handleDelete(e.id)}
              />
            ))}
          </div>
        )}
      </div>

      {gen.peekOpen && mdEditorPath && (
        <PromptPeekModal
          title="PROMPT — AI Analyze"
          fileName={fileName}
          filePath={mdEditorPath}
          storageKey={STORAGE_KEY_ANALYZE}
          presets={ANALYZE_LENSES}
          selectedPreset={gen.localPreset}
          presetPersistKey={PRESET_KEY_ANALYZE}
          cli={gen.localCli}
          onCliChange={gen.changeCli}
          onClose={() => gen.setPeekOpen(false)}
          onUseOnce={gen.runOnce}
          onPresetChange={gen.changePreset}
        />
      )}
    </div>
  )
}
