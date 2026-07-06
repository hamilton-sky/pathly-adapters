import { useSpawnCaps } from '../../../hooks/useSpawnCaps'
import s from '../Settings.module.css'

// Max concurrent CLI-engine processes. Bound to the shared spawn-caps store, so this stays in
// sync with the monitor's queue panel (both write the same set-caps IPC).
export function SpawnLimitsSection(): JSX.Element {
  const { caps, setCap } = useSpawnCaps()

  return (
    <div className={s.section}>
      <div className={s.sectionTitle}>CLI spawn limits</div>
      <div className={s.hint}>
        Max concurrent CLI-engine processes. Headless one-shots queue over the cap; interactive
        sessions are rejected. Shared live with the monitor&apos;s queue panel.
      </div>
      <div className={s.runnerFields}>
        <CapField id="cap-total" label="Total" value={caps.global} onCommit={(n) => setCap({ global: n })} />
        <CapField id="cap-headless" label="Headless" value={caps.headless} onCommit={(n) => setCap({ headless: n })} />
        <CapField id="cap-chat" label="Chat" value={caps.interactive} onCommit={(n) => setCap({ interactive: n })} />
      </div>
    </div>
  )
}

// Commit-on-blur number field; `key={value}` re-seeds the uncontrolled input when the store value
// changes (e.g. edited from the monitor), so the two surfaces show the same number.
function CapField({ id, label, value, onCommit }: { id: string; label: string; value: number; onCommit: (n: number) => void }): JSX.Element {
  return (
    <div className={s.runnerField}>
      <label className={s.runnerFieldLabel} htmlFor={id}>{label}</label>
      <input
        id={id}
        className={s.runnerInput}
        type="number"
        min={1}
        max={32}
        defaultValue={value}
        key={value}
        onBlur={(e) => onCommit(Number(e.currentTarget.value))}
        onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur() }}
      />
    </div>
  )
}
