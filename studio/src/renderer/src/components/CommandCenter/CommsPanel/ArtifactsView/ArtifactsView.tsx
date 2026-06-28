import { useState, type DragEvent } from 'react'
import { FileText, Upload } from 'lucide-react'
import type { Message } from '../../types'
import { PATHLY_DRAG_MIME } from '../../../../types'
import { AiTargetSelector } from '../../../shared/AiTargetSelector/AiTargetSelector'
import { StylePicker } from '../../../shared/StylePicker/StylePicker'
import type { AiSelection } from '../../../../services/aiRouter'
import type { SummaryStyle } from '../../../../store/commsApi'
import { MsgCard } from '../cards/MsgCard/MsgCard'
import s from './ArtifactsView.module.css'

interface Props {
  messages: Message[]
  onDelete?: (messageId: string) => void
  onSupersede?: (oldId: string, newId: string) => void
  /** OS files dropped from Explorer/Finder — copied into the feature, posted as artifacts. */
  onDropFiles?: (files: File[]) => void
  /** Project files dragged from the workspace tree — referenced in place (no copy). */
  onDropPaths?: (items: { path: string; name: string }[]) => void
  /** The AI target used to summarize dropped artifacts (app-default, persisted upstream). */
  summarySelection: AiSelection | null
  onSummarySelectionChange: (sel: AiSelection) => void
  /** The depth used to summarize dropped artifacts (app-default, persisted upstream). */
  summaryStyle: SummaryStyle
  onSummaryStyleChange: (style: SummaryStyle) => void
}

// The "Artifacts" board view: type='artifact' messages as a filtered card list,
// reusing the existing artifact card. Dropping content posts it as an artifact
// card — board content the evaluator can then read. Two drag sources:
//   • OS files (from Explorer/Finder) → copied into the feature's artifacts/.
//   • Workspace-tree files (internal drag, PATHLY_DRAG_MIME) → referenced in place.
// The toolbar selector picks the AI target that summarizes each dropped artifact
// (client-side via aiRouter); "Off" skips summarization. Conv 3 replaced the old
// localStorage backend dropdown with this unified AiTargetSelector.
export function ArtifactsView({
  messages, onDelete, onSupersede, onDropFiles, onDropPaths,
  summarySelection, onSummarySelectionChange, summaryStyle, onSummaryStyleChange,
}: Props): JSX.Element {
  const artifacts = messages.filter((m) => m.type === 'artifact')
  const [dragOver, setDragOver] = useState(false)
  const canDrop = Boolean(onDropFiles || onDropPaths)

  function handleDrop(e: DragEvent<HTMLDivElement>): void {
    if (!canDrop) return
    e.preventDefault()
    setDragOver(false)
    // Internal drag from the workspace tree carries a path, not a File object.
    const internal = e.dataTransfer.getData(PATHLY_DRAG_MIME)
    if (internal && onDropPaths) {
      try {
        const p = JSON.parse(internal) as { type?: string; sourcePath?: string; name?: string }
        if (p.type === 'file' && p.sourcePath) {
          onDropPaths([{ path: p.sourcePath, name: p.name ?? p.sourcePath.split(/[/\\]/).pop() ?? 'file' }])
          return
        }
      } catch { /* not our payload — fall through to OS files */ }
    }
    const files = Array.from(e.dataTransfer.files)
    if (files.length && onDropFiles) onDropFiles(files)
  }
  function handleDragOver(e: DragEvent<HTMLDivElement>): void {
    if (!canDrop) return
    e.preventDefault()
    setDragOver(true)
  }
  function handleDragLeave(e: DragEvent<HTMLDivElement>): void {
    if (e.currentTarget.contains(e.relatedTarget as Node)) return
    setDragOver(false)
  }

  return (
    <div
      className={s.view}
      {...(dragOver ? { 'data-dragover': '' } : {})}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
    >
      <div className={s.toolbar}>
        <div className={s.toolbarRow}>
          <label className={s.toolbarLabel} htmlFor="av-summary-target">Summarize with:</label>
          <div className={s.toolbarControl}>
            <AiTargetSelector
              id="av-summary-target"
              ariaLabel="Artifact summary AI target"
              value={summarySelection}
              onChange={onSummarySelectionChange}
              allowOff
            />
          </div>
        </div>
        <div className={s.toolbarRow}>
          <span className={s.toolbarLabel}>Depth:</span>
          <div className={s.toolbarControl}>
            <StylePicker value={summaryStyle} onChange={onSummaryStyleChange} ariaLabel="Artifact summary depth" />
          </div>
        </div>
      </div>
      {artifacts.length === 0 ? (
        <div className={s.empty}>
          <FileText size={22} />
          <p>No artifacts yet. Drop files here to add them — the evaluator can read them.</p>
        </div>
      ) : (
        artifacts.map((m) => (
          <MsgCard
            key={m.id}
            message={m}
            flash={false}
            onDelete={onDelete}
            onSupersede={onSupersede}
            siblings={messages}
          />
        ))
      )}
      {dragOver && canDrop && (
        <div className={s.dropOverlay}>
          <Upload size={26} />
          <span>Drop to add as artifacts</span>
        </div>
      )}
    </div>
  )
}
