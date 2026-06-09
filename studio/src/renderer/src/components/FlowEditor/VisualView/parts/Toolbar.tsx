import type { FlowExportTarget, CommentShape } from '../../../../types'
import { Tooltip } from '../../../ui'
import { FileText, MessageCircle } from 'lucide-react'
import { ExportControls } from './ExportControls'
import styles from './Toolbar.module.css'

interface Props {
  tab: 'visual' | 'yaml'
  onTabClick: (t: 'visual' | 'yaml') => void
  onSave: () => void
  onAddState: () => void
  onAutoLayout: () => void
  onAddNote: (shape: CommentShape) => void
  exportTarget: FlowExportTarget
  onTargetChange: (target: FlowExportTarget) => void
  hasErrors: boolean
  onPublish: () => void
}

export function Toolbar({
  tab,
  onTabClick,
  onSave,
  onAddState,
  onAutoLayout,
  onAddNote,
  exportTarget,
  onTargetChange,
  hasErrors,
  onPublish,
}: Props): JSX.Element {
  return (
    <div className={styles.toolbar}>
      <Tooltip label="Visual canvas editor" placement="bottom">
        <button type="button" className={tab === 'visual' ? styles.tabActive : styles.tab} onClick={() => onTabClick('visual')}>Visual</button>
      </Tooltip>
      <Tooltip label="YAML source editor" placement="bottom">
        <button type="button" className={tab === 'yaml' ? styles.tabActive : styles.tab} onClick={() => onTabClick('yaml')}>YAML</button>
      </Tooltip>

      <div className={styles.divider} />

      <Tooltip label="Save flow YAML" shortcut="Ctrl+S" placement="bottom">
        <button type="button" className={styles.saveBtn} onClick={onSave}>Save</button>
      </Tooltip>
      <Tooltip label="Add a new state node" placement="bottom">
        <button type="button" className={styles.ghostBtn} onClick={onAddState}>+ Add state</button>
      </Tooltip>
      <Tooltip label="Auto-arrange nodes top-to-bottom" placement="bottom">
        <button type="button" className={styles.ghostBtn} onClick={onAutoLayout}>Auto-layout</button>
      </Tooltip>

      <div className={styles.divider} />
      <Tooltip label="Add text note to canvas" placement="bottom">
        <button type="button" className={styles.noteBtn} onClick={() => onAddNote('sticky')} aria-label="Add text note">
          <FileText size={15} />
        </button>
      </Tooltip>
      <Tooltip label="Add speech bubble to canvas" placement="bottom">
        <button type="button" className={styles.noteBtn} onClick={() => onAddNote('bubble')} aria-label="Add speech bubble">
          <MessageCircle size={15} />
        </button>
      </Tooltip>

      <div className={styles.spacer} />

      <ExportControls
        exportTarget={exportTarget}
        onTargetChange={onTargetChange}
        hasErrors={hasErrors}
        onPublish={onPublish}
      />
    </div>
  )
}
