// Right-docked gallery panel (mirrors AnalysisPanel): lists the file's diagram cards;
// View opens the lightbox, Delete removes (closing on the last card). The header is one
// ActionPill — New (run) │ gear (PromptPeekModal config) │ elapsed timer + stop while a run
// is in flight — matching the board's Evaluate pill. Generation lives in useDiagramGeneration.

import React, { useEffect, useState } from 'react'
import { X, Sparkles, Image as ImageIcon } from 'lucide-react'
import {
  useUiStore,
  selectMdEditorDiagramPath,
  selectMdEditorDiagram,
} from '../../../store/uiStore'
import { useTerminalStore } from '../../../store/terminalStore'
import { useDiagramSidecar } from './useDiagramSidecar'
import { useDiagramGeneration } from './useDiagramGeneration'
import { useElapsedProgress } from '../EditorHeader/editorProgress'
import { updateDiagramLayout } from './diagramSidecar'
import type { DiagramEntry } from '../diagramTypes'
import { DIAGRAM_PRESETS, PRESET_KEY_DIAGRAM, STORAGE_KEY_DIAGRAM } from '../EditorHeader/diagramPresets'
import PromptPeekModal from '../EditorHeader/PromptPeekModal/PromptPeekModal'
import ActionPill from '../../shared/ActionPill/ActionPill'
import DiagramCard from './DiagramCard/DiagramCard'
import DiagramLightbox from './DiagramLightbox/DiagramLightbox'
import styles from './DiagramGalleryPanel.module.css'

interface Props {
  /** Override "+ New" (e.g. open the header's PromptPeekModal). */
  onNew?: () => void
  /** Override Regenerate (e.g. route through the header's confirm modal). */
  onRegenerate?: (entry: DiagramEntry) => void
  /** Override the busy flag; defaults to the file's live diagram run state. */
  busy?: boolean
}

export default function DiagramGalleryPanel({ onNew, onRegenerate, busy }: Props) {
  const mdEditorPath = useUiStore((s) => s.mdEditorPath)
  const diagramPath = useUiStore(selectMdEditorDiagramPath)
  const panelOpen = useUiStore((s) => s.mdEditorDiagramPanelOpen)
  const setPanelOpen = useUiStore((s) => s.setMdEditorDiagramPanelOpen)
  const slot = useUiStore(selectMdEditorDiagram)
  const startedAt = useTerminalStore((s) => s.tabs.find((t) => t.id === slot?.tabId)?.startedAt)

  const { diagrams, loading, reload, remove } = useDiagramSidecar(mdEditorPath)
  const gen = useDiagramGeneration(mdEditorPath)
  const [lightbox, setLightbox] = useState<DiagramEntry | null>(null)

  const diagState = slot?.status ?? 'idle'
  const isBusy = busy ?? diagState === 'running'
  const progress = useElapsedProgress(diagState === 'running' ? startedAt : undefined)

  // Refresh the cards when a run completes (file path unchanged → the sidecar hook's own
  // effect won't re-fire; watch the slot transition instead).
  useEffect(() => {
    if (slot?.status === 'success') reload()
  }, [slot?.status, reload])

  if (!diagramPath || !panelOpen) return null

  const fileName = (mdEditorPath ?? '').replace(/\\/g, '/').split('/').pop() ?? 'file'
  const handleNew = onNew ?? (() => gen.fromPreset(gen.localPreset))
  const handleRegenerate = onRegenerate ?? ((entry: DiagramEntry) => gen.fromStyle(entry.style))

  async function handleDelete(entry: DiagramEntry) {
    const remaining = await remove(entry.id)
    if (lightbox?.id === entry.id) setLightbox(null)
    if (remaining === 0) setPanelOpen(false)
  }

  function saveLayout(id: string, layout: Record<string, { x: number; y: number }>) {
    if (!mdEditorPath) return
    void updateDiagramLayout(mdEditorPath, id, layout).then(reload)
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.title}>
          Diagrams
          {diagrams.length > 0 && <span className={styles.count}>{diagrams.length}</span>}
        </span>
        <ActionPill
          state={diagState === 'success' ? 'done' : diagState}
          progress={progress}
          hasPath={!!mdEditorPath}
          title="New"
          runningVerb="Diagramming"
          mainIcon={<Sparkles size={13} />}
          idleTip="Generate a new diagram with the selected preset"
          runningTip="Generating diagram…"
          ariaName="Diagram"
          onRun={handleNew}
          onStop={() => gen.stopDiagram()}
          configTip="Preset / prompt / engine"
          onToggleConfig={() => gen.setPeekOpen(true)}
        />
        <button
          type="button"
          className={styles.closeBtn}
          onClick={() => setPanelOpen(false)}
          aria-label="Close diagrams"
        >
          <X size={14} />
        </button>
      </div>

      <div className={styles.body}>
        {loading && diagrams.length === 0 ? (
          <div className={styles.empty}>Loading…</div>
        ) : diagrams.length === 0 ? (
          <div className={styles.empty}>
            <ImageIcon size={22} />
            <span>No diagrams yet.</span>
            <button type="button" className={styles.emptyCta} onClick={handleNew} disabled={isBusy || !mdEditorPath}>
              Generate one
            </button>
          </div>
        ) : (
          <div className={styles.list}>
            {diagrams.map((d) => (
              <DiagramCard
                key={d.id}
                entry={d}
                busy={isBusy}
                onView={setLightbox}
                onAddToBoard={(e, t) => void gen.addToBoard(e, t).then((ok) => ok && reload())}
                targets={gen.boardTargets}
                onRegenerate={handleRegenerate}
                onDelete={(e) => void handleDelete(e)}
              />
            ))}
          </div>
        )}
      </div>

      {lightbox && (
        <DiagramLightbox
          entry={lightbox}
          fileName={fileName}
          onClose={() => setLightbox(null)}
          onSaveLayout={saveLayout}
        />
      )}

      {gen.peekOpen && mdEditorPath && (
        <PromptPeekModal
          title="PROMPT — Diagram"
          fileName={fileName}
          filePath={mdEditorPath}
          storageKey={STORAGE_KEY_DIAGRAM}
          presets={DIAGRAM_PRESETS}
          selectedPreset={gen.localPreset}
          presetPersistKey={PRESET_KEY_DIAGRAM}
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
