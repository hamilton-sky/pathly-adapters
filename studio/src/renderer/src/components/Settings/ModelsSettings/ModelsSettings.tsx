import { useState } from 'react'
import { usePricing } from './hooks/usePricing'
import { useModelPolicy } from './hooks/useModelPolicy'
import { useAgents } from './hooks/useAgents'
import { ModelRow } from './ModelRow/ModelRow'
import { AddRoleRow } from './AddRoleRow/AddRoleRow'
import s from './ModelsSettings.module.css'
import ss from '../Settings.module.css'

// Editor / one-shot actions are fixed app actions (not registry agents), so they stay a hard-coded
// group. The Pipeline agents come from the registry (useAgents) so a newly-created agent appears
// automatically; any other configured key shows under Custom.
const EDITOR_ROLES = ['split', 'analyze', 'diagram', 'comment', 'summarize']

export function ModelsSettings(): JSX.Element {
  const pricing = usePricing()
  const { policy, setDefault, clearDefault, setRole, clearRole } = useModelPolicy()
  const agentRoles = useAgents()
  const [extraRoles, setExtraRoles] = useState<string[]>([])

  const fixed = new Set([...agentRoles, ...EDITOR_ROLES])
  // Custom = configured keys not in a known group, plus any the user just added this session.
  const customRoles = Array.from(
    new Set([...Object.keys(policy.roles).filter((r) => !fixed.has(r)), ...extraRoles]),
  ).sort()
  const shown = new Set<string>([...fixed, ...customRoles, 'default'])

  const roleRow = (role: string): JSX.Element => (
    <ModelRow
      key={role}
      label={role}
      sel={policy.roles[role] ?? null}
      pricing={pricing}
      inheritLabel="Inherit default"
      onSet={(a, m) => setRole(role, a, m)}
      onClear={() => clearRole(role)}
    />
  )

  return (
    <div className={ss.section}>
      <div className={ss.sectionTitle}>Models</div>
      <div className={ss.hint}>
        Which company + model each agent spawns with. Precedence: per-run override → per-agent →
        global default → engine default. Leave a row on “Inherit” to fall through.
      </div>

      <ModelRow
        label="Global default"
        sel={policy.default}
        pricing={pricing}
        inheritLabel="Engine default (none)"
        onSet={setDefault}
        onClear={clearDefault}
      />

      <div className={s.groupLabel}>Agents</div>
      {agentRoles.map(roleRow)}

      <div className={s.groupLabel}>Editor / one-shot</div>
      {EDITOR_ROLES.map(roleRow)}

      <div className={s.groupLabel}>Custom</div>
      {customRoles.map(roleRow)}
      <AddRoleRow onAdd={(role) => setExtraRoles((prev) => [...prev, role])} existing={shown} />
    </div>
  )
}
