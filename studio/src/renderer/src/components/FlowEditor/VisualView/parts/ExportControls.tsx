import type { Theme } from '../../../../theme'
import type { FlowExportTarget } from '../../../../types'
import { EXPORT_TARGET_LABELS } from '../constants'
import { Tooltip } from '../../../ui'
import { makeVisualViewStyles } from '../VisualView.styles'

interface Props {
  exportTarget: FlowExportTarget
  onTargetChange: (target: FlowExportTarget) => void
  hasErrors: boolean
  onPublish: () => void
  t: Theme
}

export function ExportControls({ exportTarget, onTargetChange, hasErrors, onPublish, t }: Props): JSX.Element {
  const s = makeVisualViewStyles(t)
  return (
    <>
      <select
        aria-label="Export target"
        value={exportTarget}
        onChange={(e) => onTargetChange(e.target.value as FlowExportTarget)}
        style={s.exportSelect}
      >
        {(Object.keys(EXPORT_TARGET_LABELS) as FlowExportTarget[]).map((k) => (
          <option key={k} value={k}>{EXPORT_TARGET_LABELS[k]}</option>
        ))}
      </select>
      <Tooltip
        label={hasErrors ? 'Fix validation errors before publishing' : 'Publish flow to YAML'}
        placement="bottom"
      >
        <button
          style={hasErrors ? s.publishBtnDisabled : s.publishBtn}
          onClick={onPublish}
          disabled={hasErrors}
        >
          Publish
        </button>
      </Tooltip>
    </>
  )
}
