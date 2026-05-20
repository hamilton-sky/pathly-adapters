import { Tooltip } from '../../ui'
import s from './panel.module.css'

interface PanelHeaderProps {
  title: string
  onClose: () => void
}

export function PanelHeader({ title, onClose }: PanelHeaderProps): JSX.Element {
  return (
    <div className={s.header}>
      <span className={s.title}>{title}</span>
      <Tooltip label="Close panel" shortcut="Esc" placement="left">
        <button className={s.closeBtn} onClick={onClose} aria-label="Close panel">×</button>
      </Tooltip>
    </div>
  )
}
