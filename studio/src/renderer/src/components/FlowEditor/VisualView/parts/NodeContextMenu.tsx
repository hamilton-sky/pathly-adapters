import type { Theme } from '../../../../theme'
import { makeVisualViewStyles } from '../VisualView.styles'

interface Props {
  x: number
  y: number
  nodeId: string
  onClose: () => void
  onRemove: (nodeId: string) => void
  t: Theme
}

export function NodeContextMenu({ x, y, nodeId, onClose, onRemove, t }: Props): JSX.Element {
  const s = makeVisualViewStyles(t)
  return (
    <>
      <div style={s.contextBackdrop} onClick={onClose} />
      {/* position is dynamic — left/top must stay inline */}
      <div style={{ ...s.contextMenu, left: x, top: y }}>
        <button style={s.contextMenuBtn} onClick={() => onRemove(nodeId)}>
          Remove from canvas
        </button>
      </div>
    </>
  )
}
