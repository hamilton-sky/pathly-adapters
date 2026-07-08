import { useState, type DragEvent } from 'react'
import { FileText, Upload } from 'lucide-react'
import type { Message } from '../../types'
import { PATHLY_DRAG_MIME } from '../../../../types'
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
}

const WORKSPACE_TREE_DRAG_MIME = 'application/x-pathly-ws-move'

function droppedPathFromPathlyPayload(raw: string): { path: string; name: string } | null {
  try {
    const p = JSON.parse(raw) as {
      dragType?: string
      type?: string
      sourcePath?: string
      src?: string
      isFolder?: boolean
      name?: string
      path?: string[]
    }
    if (p.isFolder || p.type === 'folder') return null
    const path =
      p.sourcePath ??
      p.src ??
      (p.dragType === 'canvas' && p.path?.length ? p.path[0] : undefined)
    if (!path) return null
    return { path, name: p.name ?? path.split(/[/\\]/).pop() ?? 'file' }
  } catch {
    return null
  }
}

// The "Artifacts" board view: type='artifact' messages as a filtered card list,
// reusing the existing artifact card. Dropping content posts it as an artifact
// card — board content the evaluator can then read. Two drag sources:
//   • OS files (from Explorer/Finder) → copied into the feature's artifacts/.
//   • Workspace-tree files (internal drag, PATHLY_DRAG_MIME) → referenced in place.
// The AI target + depth that summarize each dropped artifact are configured via the
// SummaryConfig popover in the board's view-toggle row (top right), not here.
export function ArtifactsView({
  messages, onDelete, onSupersede, onDropFiles, onDropPaths,
}: Props): JSX.Element {
  const artifacts = messages.filter((m) => m.type === 'artifact')
  const [dragOver, setDragOver] = useState(false)
  const canDrop = Boolean(onDropFiles || onDropPaths)

  function handleDrop(e: DragEvent<HTMLDivElement>): void {
    if (!canDrop) return
    e.preventDefault()
    setDragOver(false)
    // Internal drags carry a path, not a File object. The current sidebar has
    // two sources: LibraryCatalog uses PATHLY_DRAG_MIME, while WorkspaceTree
    // uses its move MIME for tree reordering.
    const internal = e.dataTransfer.getData(PATHLY_DRAG_MIME) || e.dataTransfer.getData(WORKSPACE_TREE_DRAG_MIME)
    if (internal && onDropPaths) {
      const item = droppedPathFromPathlyPayload(internal)
      if (item) {
        onDropPaths([item])
        return
      }
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
