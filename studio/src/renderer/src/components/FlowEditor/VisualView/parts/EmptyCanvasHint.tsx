import type { Theme } from '../../../../theme'
import { makeVisualViewStyles } from '../VisualView.styles'

interface Props {
  t: Theme
}

export function EmptyCanvasHint({ t }: Props): JSX.Element {
  const s = makeVisualViewStyles(t)
  return (
    <div style={s.emptyOverlay}>
      <div style={s.emptyBox}>
        <div style={s.emptyText}>Drag an agent from the library to start</div>
        <div style={s.emptySubtext}>
          or click <strong style={s.emptySubtextAccent}>+ Add state</strong> in the toolbar
        </div>
      </div>
    </div>
  )
}
