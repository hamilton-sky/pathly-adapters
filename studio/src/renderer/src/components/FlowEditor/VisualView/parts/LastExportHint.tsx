import type { Theme } from '../../../../theme'
import type { FlowExportRecord } from '../../../../types'
import { makeVisualViewStyles } from '../VisualView.styles'

interface Props {
  lastExport: FlowExportRecord
  t: Theme
}

export function LastExportHint({ lastExport, t }: Props): JSX.Element {
  const s = makeVisualViewStyles(t)
  const minsAgo = Math.round((Date.now() - lastExport.at.getTime()) / 60000) || '<1'
  return (
    <div style={s.lastExportHint}>
      Last: {lastExport.path} ✓ {minsAgo}m ago
    </div>
  )
}
