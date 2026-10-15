import { useHqActionAvailability } from '../hooks/useHqActionAvailability'
import s from '../Settings.module.css'
import styles from './HqActionsSettings.module.css'

/** Which operator actions HQ's local model may propose (pathly/features/local-operator).
 *  The catalog is curated in code — never raw API access — and every action still
 *  waits for a Run click on its card in the chat. */
export function HqActionsSettings(): JSX.Element {
  const { catalog, failed, saving, isDefault, setAvailable, resetDefaults } = useHqActionAvailability()

  return (
    <div className={s.section}>
      <div className={s.sectionTitle}>HQ actions</div>
      <div className={s.hint}>
        What HQ&apos;s local model may propose. Each proposal is a card in the chat that runs only when you
        click Run. Pick up to {catalog?.max_enabled ?? 8} for a question in the composer&apos;s Actions tab.
      </div>
      {failed && <div className={styles.error} role="alert">Could not load or save HQ actions — is the Pathly server running?</div>}
      {catalog?.domains.map((d) => {
        const actions = catalog.actions.filter((a) => a.domain === d.id)
        if (!actions.length) return null
        return (
          <fieldset key={d.id} className={styles.group} disabled={saving}>
            <legend className={styles.legend}>{d.label}</legend>
            {actions.map((a) => (
              <label key={a.name} className={styles.row}>
                <input
                  type="checkbox"
                  className={styles.check}
                  checked={a.available}
                  onChange={(e) => setAvailable(a.name, e.target.checked)}
                />
                <span className={styles.name}>{a.label}</span>
                {a.runs_on === 'studio' && <span className={styles.tag}>runs in Studio</span>}
                <span className={styles.risk}>{a.risk.join(' · ')}</span>
              </label>
            ))}
          </fieldset>
        )
      })}
      {catalog && (
        <div className={styles.footer}>
          <span className={styles.never}>
            Never offered: answering agent questions, directives, settings and secrets, files and shell.
          </span>
          {!isDefault && (
            <button type="button" className={styles.reset} onClick={resetDefaults} disabled={saving}>
              Reset to defaults
            </button>
          )}
        </div>
      )}
    </div>
  )
}
