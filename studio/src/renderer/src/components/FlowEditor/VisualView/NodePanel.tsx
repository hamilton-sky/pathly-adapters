import type { Theme } from '../../../theme'
import type { FlowYaml } from '../../../types'
import { makePanelStyles } from '../shared/panelStyles'
import { PanelHeader } from '../shared/PanelHeader'

interface NodePanelProps {
  stateId: string
  data: FlowYaml
  onAgentChange: (stateId: string, value: string) => void
  onAddRule: (source: string) => void
  onClose: () => void
  t: Theme
}

export function NodePanel({ stateId, data, onAgentChange, onAddRule, onClose, t }: NodePanelProps): JSX.Element {
  const panelStyles = makePanelStyles(t)
  const rules = (data.transition_rules as Record<string, Record<string, string>> | undefined) ?? {}
  const relevantRules = Object.entries(rules).filter(([, mapping]) =>
    Object.prototype.hasOwnProperty.call(mapping, stateId)
  )

  return (
    <div style={panelStyles.panel}>
      <PanelHeader title={stateId} onClose={onClose} t={t} />
      <label style={panelStyles.label}>Agent</label>
      <input
        style={panelStyles.input}
        value={data.agent_map[stateId] ?? ''}
        onChange={(e) => onAgentChange(stateId, e.target.value)}
      />
      <label style={panelStyles.label}>Transition Rules</label>
      {relevantRules.map(([artifact, mapping]) => (
        <div key={artifact} style={panelStyles.ruleRow}>
          <span style={panelStyles.ruleArtifact}>{artifact}</span>
          <span style={panelStyles.ruleArrow}>→</span>
          <span style={panelStyles.ruleTarget}>{mapping[stateId]}</span>
        </div>
      ))}
      <button style={panelStyles.addBtn} onClick={() => onAddRule(stateId)}>
        + Add rule
      </button>
    </div>
  )
}
