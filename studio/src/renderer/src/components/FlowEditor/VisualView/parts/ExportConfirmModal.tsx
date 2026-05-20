import type { Theme } from '../../../../theme'
import type { FlowExportTarget } from '../../../../types'
import { EXPORT_TARGET_DESCRIPTIONS } from '../constants'
import { makeVisualViewStyles } from '../VisualView.styles'

interface Props {
  exportTarget: FlowExportTarget
  onCancel: () => void
  onConfirm: () => void
  t: Theme
}

export function ExportConfirmModal({ exportTarget, onCancel, onConfirm, t }: Props): JSX.Element {
  const s = makeVisualViewStyles(t)
  return (
    <div style={s.confirmOverlay}>
      <div style={s.confirmModal}>
        <p style={s.confirmText}>This flow has validation warnings. Publish anyway?</p>
        <p style={s.confirmSubtext}>{EXPORT_TARGET_DESCRIPTIONS[exportTarget]}</p>
        <div style={s.confirmActions}>
          <button style={s.cancelBtn} onClick={onCancel}>Cancel</button>
          <button style={s.confirmBtn} onClick={onConfirm}>Publish anyway</button>
        </div>
      </div>
    </div>
  )
}
