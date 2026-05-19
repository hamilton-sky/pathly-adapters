import type { Theme } from '../../../theme'
import { Tooltip } from '../../ui'
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
      <Tooltip label="Close panel" shortcut="Esc" placement="left">
        <button style={panelStyles.closeBtn} onClick={onClose} aria-label="Close panel">×</button>
      </Tooltip>
    </div>
  )
}
