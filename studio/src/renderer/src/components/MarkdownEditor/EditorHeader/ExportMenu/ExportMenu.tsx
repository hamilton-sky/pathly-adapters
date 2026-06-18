import { useState, useEffect, useRef } from 'react'
import { Download, FileUp, FileDown, ClipboardCopy, PackageCheck, ChevronDown } from 'lucide-react'
import { Tooltip } from '../../../ui'
import { useToastStore } from '../../../../store/toastStore'
import styles from './ExportMenu.module.css'

type InstallState = 'idle' | 'success' | 'error'

interface Props {
  /** Current document path. The menu reads content fresh from disk at action time. */
  path: string | null
  /** Show the skill-only "Install → adapters" item (composes + writes to adapter dirs). */
  isSkillOrAgent: boolean
  /** State of the install action, for the item's label/colour. */
  installState: InstallState
  /** The existing "Export Skill" handler (compose + PUT /skills/export). */
  onInstallSkill: () => void
  /** Hide the trigger's text label when the header is in compact mode. */
  compact?: boolean
}

// Export ▾ — one menu of "get this markdown out" actions, shared by every document.
// Save-as / Download / Copy apply to any md; Install → adapters is skill/agent only.
// Opens downward, right-aligned (it lives at the far right of the top header bar).
export default function ExportMenu({ path, isSkillOrAgent, installState, onInstallSkill, compact }: Props) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const toast = (msg: string, kind: 'success' | 'error') =>
    useToastStore.getState().push(msg, kind, { category: 'db_crud' })

  // Source of truth for export is the saved file — read it fresh. Save first if you
  // have unsaved edits in the editor/cells.
  const readContent = async (): Promise<string | null> => {
    if (!path) return null
    const content = await window.pathly.fs.read(path)
    if (content == null) { toast('File not found on disk', 'error'); return null }
    return content
  }

  const handleSaveAs = async () => {
    setOpen(false)
    if (!path) return
    const content = await readContent()
    if (content == null) return
    const saved = await window.pathly.fs.saveDialog(path, content)
    if (saved) toast('Saved a copy', 'success')
  }

  const handleDownload = async () => {
    setOpen(false)
    if (!path) return
    const content = await readContent()
    if (content == null) return
    const saved = await window.pathly.fs.saveDialog(path, content, true)
    if (saved) toast('Downloaded a copy', 'success')
  }

  const handleCopy = async () => {
    setOpen(false)
    const content = await readContent()
    if (content == null) return
    await window.pathly.clipboard.write(content)
    toast('Copied markdown to clipboard', 'success')
  }

  const handleInstall = () => {
    setOpen(false)
    onInstallSkill()
  }

  const installLabel =
    installState === 'success' ? 'Installed' : installState === 'error' ? 'Install failed' : 'Install skill → adapters'

  return (
    <div className={styles.wrap} ref={ref}>
      <Tooltip label="Export this document" placement="bottom">
        <button
          type="button"
          className={styles.trigger}
          aria-haspopup="menu"
          {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
          onClick={() => setOpen((o) => !o)}
          disabled={!path}
        >
          <Download size={14} />
          {!compact && <span className={styles.label}>Export</span>}
          <ChevronDown size={12} className={styles.chev} />
        </button>
      </Tooltip>

      {open && (
        <div className={styles.menu} role="menu">
          <button type="button" role="menuitem" className={styles.item} onClick={handleSaveAs}>
            <FileUp size={13} />Save as…
          </button>
          <button type="button" role="menuitem" className={styles.item} onClick={handleDownload}>
            <FileDown size={13} />Download a copy
          </button>
          <button type="button" role="menuitem" className={styles.item} onClick={handleCopy}>
            <ClipboardCopy size={13} />Copy to clipboard
          </button>
          {isSkillOrAgent && (
            <>
              <div className={styles.divider} />
              <button
                type="button"
                role="menuitem"
                className={styles.item}
                data-state={installState}
                onClick={handleInstall}
              >
                <PackageCheck size={13} />{installLabel}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
