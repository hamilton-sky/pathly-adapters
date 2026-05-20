import type { FlowExportTarget } from '../../../../types'
import type { Theme } from '../../../../theme'
import { Tooltip } from '../../../ui'
import { makeVisualViewStyles } from '../VisualView.styles'
import { ExportControls } from './ExportControls'

interface Props {
  tab: 'visual' | 'yaml'
  onTabClick: (t: 'visual' | 'yaml') => void
  onSave: () => void
  onAddState: () => void
  onAutoLayout: () => void
  exportTarget: FlowExportTarget
  onTargetChange: (target: FlowExportTarget) => void
  hasErrors: boolean
  onPublish: () => void
  t: Theme
}

export function Toolbar({
  tab,
  onTabClick,
  onSave,
  onAddState,
  onAutoLayout,
  exportTarget,
  onTargetChange,
  hasErrors,
  onPublish,
  t,
}: Props): JSX.Element {
  const s = makeVisualViewStyles(t)
  return (
    <div style={s.toolbar}>
      <Tooltip label="Visual canvas editor" placement="bottom">
        <button style={tab === 'visual' ? s.tabActive : s.tab} onClick={() => onTabClick('visual')}>Visual</button>
      </Tooltip>
      <Tooltip label="YAML source editor" placement="bottom">
        <button style={tab === 'yaml' ? s.tabActive : s.tab} onClick={() => onTabClick('yaml')}>YAML</button>
      </Tooltip>

      <div style={s.toolbarDivider} />

      <Tooltip label="Save flow YAML" shortcut="Ctrl+S" placement="bottom">
        <button style={s.saveBtn} onClick={onSave}>Save</button>
      </Tooltip>
      <Tooltip label="Add a new state node" placement="bottom">
        <button style={s.ghostBtn} onClick={onAddState}>+ Add state</button>
      </Tooltip>
      <Tooltip label="Auto-arrange nodes left-to-right" placement="bottom">
        <button style={s.ghostBtn} onClick={onAutoLayout}>Auto-layout</button>
      </Tooltip>

      <div style={s.toolbarSpacer} />

      <ExportControls
        exportTarget={exportTarget}
        onTargetChange={onTargetChange}
        hasErrors={hasErrors}
        onPublish={onPublish}
        t={t}
      />
    </div>
  )
}
