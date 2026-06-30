// Right-docked gallery panel — shares the slot/shape with AnalysisPanel. Lists the
// current file's diagram cards from the sidecar, opens the lightbox on View, removes
// cards on Delete (closing itself when the last card goes), and regenerates / adds
// diagrams via a panel-local spawn-hook instance.
//
// New / Regenerate are self-contained here (seeded from the persisted CLI + preset),
// so the panel works whether or not EditorHeader passes handlers. Pass onNew /
// onRegenerate to override with the header's confirm-modal flow instead.
//
// Path assumes: src/components/MarkdownEditor/DiagramGalleryPanel/DiagramGalleryPanel.tsx

import React, { useEffect, useState } from 'react'
import { X, Plus, Image as ImageIcon } from 'lucide-react'
import {
  useUiStore,
  selectMdEditorDiagramPath,
  selectMdEditorDiagram,
} from '../../../store/uiStore'
import { useDiagramSidecar } from './useDiagramSidecar'
import { updateDiagramLayout } from './diagramSidecar'
import { type DiagramEntry, type DiagramStyle, sidecarPathFor } from '../diagramTypes'
import { useEditorDiagramAction } from '../EditorHeader/hooks/useEditorDiagramAction'
import { loadEditorCli, loadPreset } from '../EditorHeader/editorCli'
import { DIAGRAM_PRESETS, CLI_KEY_DIAGRAM, PRESET_KEY_DIAGRAM } from '../EditorHeader/diagramPresets'
import { resolvePrompt } from '../../shared/PromptActionConfig/presetTypes'
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

  const { diagrams, loading, reload, remove } = useDiagramSidecar(mdEditorPath)
  const [lightbox, setLightbox] = useState<DiagramEntry | null>(null)

  // Panel-local generation — seeded once from the persisted CLI + preset so the panel
  // can New/Regenerate without prop-drilling from the header.
  const [localCli] = useState(() => loadEditorCli(CLI_KEY_DIAGRAM))
  const [localPreset] = useState(() => loadPreset(PRESET_KEY_DIAGRAM))
  const { handleDiagram } = useEditorDiagramAction(mdEditorPath, null, () => {}, localCli, localPreset)

  const isBusy = busy ?? slot?.status === 'running'

  // Refresh the cards when a run completes (the file path is unchanged, so the sidecar
  // hook's own filePath effect won't re-fire — watch the slot transition instead).
  useEffect(() => {
    if (slot?.status === 'success') reload()
  }, [slot?.status, reload])

  if (!diagramPath || !panelOpen) return null

  const fileName = (mdEditorPath ?? '').replace(/\\/g, '/').split('/').pop() ?? 'file'

  // Build a prompt for a given style and spawn a run (append, not overwrite).
  function generate(style: DiagramStyle) {
    if (!mdEditorPath) return
    const preset = DIAGRAM_PRESETS.find((p) => p.style === style) ?? DIAGRAM_PRESETS[0]
    const norm = mdEditorPath.replace(/\\/g, '/')
    const prompt = resolvePrompt(preset.prompt, { FILE: norm, SIDECAR: sidecarPathFor(norm) })
    void handleDiagram(prompt)
  }

  const handleNew = onNew ?? (() => generate(DIAGRAM_PRESETS[0].style))
  const handleRegenerate = onRegenerate ?? ((entry: DiagramEntry) => generate(entry.style))

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
        <span className={styles.title}>Diagrams</span>
        <button type="button" className={styles.newBtn} onClick={handleNew} disabled={isBusy || !mdEditorPath}>
          <Plus size={12} />
          New
        </button>
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
    </div>
  )
}
