import { usePricing } from './hooks/usePricing'
import { useModelPolicy } from './hooks/useModelPolicy'
import { ModelRow } from './ModelRow/ModelRow'
import s from './ModelsSettings.module.css'
import ss from '../Settings.module.css'

// The agent/telemetry identities a spawn can carry, grouped for the UI. Kept in sync with the
// resolver keys — resolve_agent_model(role) in db/queries/app_settings.py.
const PIPELINE_ROLES = [
  'architect', 'planner', 'builder', 'reviewer', 'tester', 'scout', 'designer', 'director', 'evaluator',
]
const EDITOR_ROLES = ['split', 'analyze', 'diagram', 'comment', 'summarize']

export function ModelsSettings(): JSX.Element {
  const pricing = usePricing()
  const { policy, setDefault, clearDefault, setRole, clearRole } = useModelPolicy()

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

      <div className={s.groupLabel}>Pipeline</div>
      {PIPELINE_ROLES.map((role) => (
        <ModelRow
          key={role}
          label={role}
          sel={policy.roles[role] ?? null}
          pricing={pricing}
          inheritLabel="Inherit default"
          onSet={(a, m) => setRole(role, a, m)}
          onClear={() => clearRole(role)}
        />
      ))}

      <div className={s.groupLabel}>Editor / one-shot</div>
      {EDITOR_ROLES.map((role) => (
        <ModelRow
          key={role}
          label={role}
          sel={policy.roles[role] ?? null}
          pricing={pricing}
          inheritLabel="Inherit default"
          onSet={(a, m) => setRole(role, a, m)}
          onClear={() => clearRole(role)}
        />
      ))}
    </div>
  )
}
