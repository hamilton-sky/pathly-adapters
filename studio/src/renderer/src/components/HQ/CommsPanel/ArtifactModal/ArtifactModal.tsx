import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, SquarePen, FileText } from 'lucide-react'
import type { Message } from '../../../CommandCenter/types'
import { useFocusTrap } from '../../../../hooks/useFocusTrap'
import { readFile } from '../../../../services/pathlyApi'
import { fetchArtifacts, relativeTime, type ArtifactRow } from '../../../../store/commsApi'
import { useUiStore } from '../../../../store/uiStore'
import { useProjectStore } from '../../../../store/projectStore'
import s from './ArtifactModal.module.css'

interface Props {
  message: Message
  onClose: () => void
}

const PREVIEW_LINES = 24

/**
 * Artifact details modal — metadata for the artifact message plus a live preview
 * read from the file, and an "Open in editor" action. Stored fields (stored
 * token_count, version, last-edit) come from the comms_artifacts side-table when
 * present; size/lines/preview are always computed live from the file. version /
 * last-edit stay hidden until the editor-save + versioning hooks populate them.
 */
export function ArtifactModal({ message: m, onClose }: Props): JSX.Element {
  const boxRef = useRef<HTMLDivElement>(null)
  useFocusTrap(boxRef)
  const [content, setContent] = useState<string | null>(null)
  const [loadErr, setLoadErr] = useState(false)
  const [meta, setMeta] = useState<ArtifactRow | null>(null)

  useEffect(() => {
    let alive = true
    if (!m.artifactPath) { setLoadErr(true); return }
    readFile(m.artifactPath)
      .then((txt) => { if (alive) { if (txt == null) setLoadErr(true); else setContent(txt) } })
      .catch(() => { if (alive) setLoadErr(true) })
    return () => { alive = false }
  }, [m.artifactPath])

  // Pull stored metadata from the comms_artifacts table (newest row wins).
  useEffect(() => {
    let alive = true
    fetchArtifacts(m.id).then((rows) => { if (alive) setMeta(rows[0] ?? null) })
    return () => { alive = false }
  }, [m.id])

  useEffect(() => {
    function onKey(e: KeyboardEvent): void { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const bytes = content != null ? new Blob([content]).size : null
  const tokenEst = content != null ? Math.ceil(content.length / 4) : null
  const lines = content != null ? content.split('\n').length : null
  const preview = content != null ? content.split('\n').slice(0, PREVIEW_LINES).join('\n') : ''
  // Prefer the stored exact token_count; fall back to the live estimate.
  const storedTokens = meta?.token_count ?? null
  const tokenText = storedTokens != null
    ? storedTokens.toLocaleString()
    : tokenEst != null ? `~${tokenEst.toLocaleString()}` : loadErr ? '—' : '…'

  function openInEditor(): void {
    if (!m.artifactPath) return
    const name = m.artifactPath.split(/[/\\]/).pop() ?? m.artifactPath
    useProjectStore.getState().setSelectedItem({ name, path: m.artifactPath, type: 'plan' })
    useUiStore.getState().setActivePanel('editor')
    onClose()
  }

  return createPortal(
    <div className={s.backdrop} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div ref={boxRef} role="dialog" aria-modal="true" aria-label="Artifact details" className={s.modal}>
        <header className={s.head}>
          <FileText size={16} />
          <span className={s.title}>{m.artifact ?? 'Artifact'}</span>
          <button type="button" className={s.close} onClick={onClose} aria-label="Close"><X size={15} /></button>
        </header>

        <div className={s.body}>
          <div className={s.metaGrid}>
            <span className={s.metaLabel}>Created by</span><span className={s.metaVal}>{m.from}</span>
            <span className={s.metaLabel}>Created</span><span className={s.metaVal}>{m.time} ago</span>
            <span className={s.metaLabel}>Type</span><span className={s.metaVal}>{m.atype ?? 'md'}</span>
            {m.stage && (<><span className={s.metaLabel}>Stage</span><span className={s.metaVal}>{m.stage}</span></>)}
            <span className={s.metaLabel}>Size</span>
            <span className={s.metaVal}>{bytes != null ? `${bytes.toLocaleString()} bytes` : loadErr ? '—' : '…'}</span>
            <span className={s.metaLabel}>~Tokens</span>
            <span className={s.metaVal}>{tokenText}</span>
            <span className={s.metaLabel}>Lines</span>
            <span className={s.metaVal}>{lines != null ? lines.toLocaleString() : loadErr ? '—' : '…'}</span>
            {meta?.version != null && meta.version > 1 && (
              <><span className={s.metaLabel}>Version</span><span className={s.metaVal}>v{meta.version}</span></>
            )}
            {meta?.last_edit_at && (
              <>
                <span className={s.metaLabel}>Last edited</span>
                <span className={s.metaVal}>{relativeTime(meta.last_edit_at)} ago{meta.last_edit_by ? ` · ${meta.last_edit_by}` : ''}</span>
              </>
            )}
            <span className={s.metaLabel}>Path</span><span className={s.metaPath}>{m.artifactPath ?? '—'}</span>
          </div>

          {m.text && (
            <>
              <span className={s.sectionLabel}>Summary</span>
              <div className={s.summary}>{m.text}</div>
            </>
          )}

          <span className={s.sectionLabel}>
            Preview{lines != null ? ` · first ${Math.min(PREVIEW_LINES, lines)} of ${lines.toLocaleString()} lines` : ''}
          </span>
          <pre className={s.preview}>
            {loadErr ? 'Could not read the file.' : content == null ? 'Loading…' : preview}
          </pre>
        </div>

        <footer className={s.foot}>
          <span className={s.spacer} />
          <button type="button" className={s.btnQuiet} onClick={onClose}>Close</button>
          {m.artifactPath && (
            <button type="button" className={s.btnOpen} onClick={openInEditor}>
              <SquarePen size={13} /> Open in editor
            </button>
          )}
        </footer>
      </div>
    </div>,
    document.body,
  )
}
