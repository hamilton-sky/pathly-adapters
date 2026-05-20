import type { Theme } from '../../../../theme'
import type { FlowExportRecord } from '../../../../types'
import { makeVisualViewStyles } from '../VisualView.styles'

interface Props {
  message: string
  lastExport: FlowExportRecord | null
  t: Theme
}

export function ExportToast({ message, lastExport, t }: Props): JSX.Element {
  const s = makeVisualViewStyles(t)
  return (
    <div style={s.toast}>
      {message}
      {lastExport && (
        <button
          style={s.toastCopyBtn}
          onClick={() => { void navigator.clipboard.writeText(lastExport.path) }}
        >
          Copy path
        </button>
      )}
    </div>
  )
}
