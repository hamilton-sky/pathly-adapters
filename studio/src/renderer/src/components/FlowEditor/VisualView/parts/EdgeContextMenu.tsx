import type { Theme } from '../../../../theme'
import { makeVisualViewStyles } from '../VisualView.styles'

interface Props {
  x: number
  y: number
  source: string
  target: string
  onClose: () => void
  onRemove: (source: string, target: string) => void
  t: Theme
}

export function EdgeContextMenu({ x, y, source, target, onClose, onRemove, t }: Props): JSX.Element {
  const s = makeVisualViewStyles(t)
  return (
    <>
      <div style={s.contextBackdrop} onClick={onClose} />
      {/* position is dynamic — left/top must stay inline */}
      <div style={{ ...s.contextMenu, minWidth: 180, left: x, top: y }}>
        <button style={s.contextMenuBtn} onClick={() => onRemove(source, target)}>
          Delete connection
        </button>
      </div>
    </>
  )
}
