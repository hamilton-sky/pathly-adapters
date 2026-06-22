import { useState, type DragEvent, type ChangeEvent } from 'react'
import { FileText, Upload } from 'lucide-react'
import type { Message } from '../../../CommandCenter/types'
import { PATHLY_DRAG_MIME } from '../../../../types'
import { CommsMsgCard } from '../CommsMsgCard'
import s from './ArtifactsView.module.css'

const LS_KEY = 'pathly.comms.uploadSummary'

function readStoredBackend(): string {
  try { return localStorage.getItem(LS_KEY) ?? '' } catch { return '' }
}

interface Props {
  messages: Message[]
  onDelete?: (messageId: string) => void
  onSupersede?: (oldId: string, newId: string) => void
  /** OS files dropped from Explorer/Finder — copied into the feature, posted as artifacts. */
  onDropFiles?: (files: File[]) => void
  /** Project files dragged from the workspace tree — referenced in place (no copy). */
  onDropPaths?: (items: { path: string; name: string }[]) => void
}

// The "Artifacts" board view: type='artifact' messages as a filtered card list,
// reusing the existing artifact card. Dropping content posts it as an artifact
// card — board content the evaluator can then read. Two drag sources:
//   • OS files (from Explorer/Finder) → copied into the feature's artifacts/.
//   • Workspace-tree files (internal drag, PATHLY_DRAG_MIME) → referenced in place.
export function ArtifactsView({ messages, onDelete, onSupersede, onDropFiles, onDropPaths }: Props): JSX.Element {
  const artifacts = messages.filter((m) => m.type === 'artifact')
  const [dragOver, setDragOver] = useState(false)
  const [uploadBackend, setUploadBackend] = useState<string>(readStoredBackend)
  const canDrop = Boolean(onDropFiles || onDropPaths)

  function handleBackendChange(e: ChangeEvent<HTMLSelectElement>): void {
    const val = e.target.value
    setUploadBackend(val)
    try { localStorage.setItem(LS_KEY, val) } catch { /* storage unavailable */ }
  }

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
        <label className={s.toolbarLabel} htmlFor="av-upload-backend">Upload summary:</label>
        <select
          id="av-upload-backend"
          className={s.backendSelect}
          aria-label="Per-upload summary backend"
          value={uploadBackend}
          onChange={handleBackendChange}
        >
          <option value="">Use default</option>
          <option value="minilm">Off</option>
          <option value="ollama">Local</option>
          <option value="haiku">Haiku</option>
        </select>
      </div>
      {artifacts.length === 0 ? (
        <div className={s.empty}>
          <FileText size={22} />
          <p>No artifacts yet. Drop files here to add them — the evaluator can read them.</p>
        </div>
      ) : (
        artifacts.map((m) => (
          <CommsMsgCard
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
