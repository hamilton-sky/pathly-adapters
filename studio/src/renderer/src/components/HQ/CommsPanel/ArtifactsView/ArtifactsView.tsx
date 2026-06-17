import { useState, type DragEvent } from 'react'
import { FileText, Upload } from 'lucide-react'
import type { Message } from '../../../CommandCenter/types'
import { CommsMsgCard } from '../CommsMsgCard'
import s from './ArtifactsView.module.css'

interface Props {
  messages: Message[]
  onDelete?: (messageId: string) => void
  onSupersede?: (oldId: string, newId: string) => void
  /** Files dropped onto the view — copied into the feature and posted as artifacts. */
  onDropFiles?: (files: File[]) => void
}

// The "Artifacts" board view: type='artifact' messages as a filtered card list,
// reusing the existing artifact card. Dropping files anywhere on the view copies
// them into the feature's artifacts/ and posts them as artifact cards — board
// content the evaluator can then read.
export function ArtifactsView({ messages, onDelete, onSupersede, onDropFiles }: Props): JSX.Element {
  const artifacts = messages.filter((m) => m.type === 'artifact')
  const [dragOver, setDragOver] = useState(false)

  function handleDrop(e: DragEvent<HTMLDivElement>): void {
    if (!onDropFiles) return
    e.preventDefault()
    setDragOver(false)
    const files = Array.from(e.dataTransfer.files)
    if (files.length) onDropFiles(files)
  }
  function handleDragOver(e: DragEvent<HTMLDivElement>): void {
    if (!onDropFiles) return
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
      {dragOver && onDropFiles && (
        <div className={s.dropOverlay}>
          <Upload size={26} />
          <span>Drop to add as artifacts</span>
        </div>
      )}
    </div>
  )
}
