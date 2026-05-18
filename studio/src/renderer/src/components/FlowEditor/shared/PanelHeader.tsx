import type { Theme } from '../../../theme'
import { makePanelStyles } from './panelStyles'

interface PanelHeaderProps {
  title: string
  onClose: () => void
  t: Theme
}

export function PanelHeader({ title, onClose, t }: PanelHeaderProps): JSX.Element {
  const panelStyles = makePanelStyles(t)
  return (
    <div style={panelStyles.header}>
      <span style={panelStyles.title}>{title}</span>
      <button style={panelStyles.closeBtn} onClick={onClose}>x</button>
    </div>
  )
}
