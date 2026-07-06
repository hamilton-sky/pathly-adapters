import type { Theme } from '../../../../theme'
import type { FlowExportRecord } from '../../../../types'
import { makeVisualViewStyles } from '../VisualView.styles'
import { Timestamp } from '../../../Timestamp/Timestamp'

interface Props {
  lastExport: FlowExportRecord
  t: Theme
}

export function LastExportHint({ lastExport, t }: Props): JSX.Element {
  const s = makeVisualViewStyles(t)
  return (
    <div style={s.lastExportHint}>
      Last: {lastExport.path} ✓ <Timestamp value={lastExport.at} />
    </div>
  )
}
