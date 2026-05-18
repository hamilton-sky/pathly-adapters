import type { Theme } from '../../../theme'
import type { FlowYaml } from '../../../types'
import { makePanelStyles } from '../shared/panelStyles'
import { PanelHeader } from '../shared/PanelHeader'

interface EdgePanelProps {
  source: string
  target: string
  data: FlowYaml
  onAddAction: (source: string, target: string) => void
  onClose: () => void
  t: Theme
}

export function EdgePanel({ source, target, data, onAddAction, onClose, t }: EdgePanelProps): JSX.Element {
  const panelStyles = makePanelStyles(t)
  const actions = (data.transition_actions as Record<string, Array<{ skill: string; message: string }>> | undefined) ?? {}
  const key = `${source}->${target}`
  const actionList = actions[key] ?? []

  return (
    <div style={panelStyles.panel}>
      <PanelHeader title={`${source} → ${target}`} onClose={onClose} t={t} />
      <label style={panelStyles.label}>Transition Actions</label>
      {actionList.map((action, i) => (
        <div key={i} style={panelStyles.actionRow}>
          <span style={panelStyles.ruleArtifact}>{action.skill || '(skill)'}</span>
          <span style={panelStyles.ruleTarget}>{action.message || '(message)'}</span>
        </div>
      ))}
      <button style={panelStyles.addBtn} onClick={() => onAddAction(source, target)}>
        + Add action
      </button>
    </div>
  )
}
