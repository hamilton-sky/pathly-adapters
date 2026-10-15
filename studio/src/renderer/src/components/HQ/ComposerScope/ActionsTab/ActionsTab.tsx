import { useId } from 'react'
import { MAX_HQ_ACTIONS } from '../../../../store/hqActionsStore'
import type { useActionSelection } from '../hooks/useActionSelection'
import styles from './ActionsTab.module.css'

type Selection = ReturnType<typeof useActionSelection>

/** The operator actions the next question may propose, grouped by domain, each
 *  with its risk in words. At the cap, unticked rows stay focusable but
 *  aria-disabled with the reason; nothing is ever auto-unticked. */
export function ActionsTab({ sel }: { sel: Selection }): JSX.Element {
  const capId = useId()
  const { catalog } = sel
  if (!catalog) return <div className={styles.note}>Loading actions… (needs the Pathly server)</div>

  const presets = catalog.presets.filter((p) => p.actions.some((n) => sel.available.some((a) => a.name === n)))
  return (
    <div className={styles.wrap}>
      {!sel.builtIn && (
        <div className={styles.warn} role="note">
          Actions need the built-in model. With Ollama or Brightsky selected, HQ stays read-only.
        </div>
      )}
      {sel.available.length === 0 ? (
        <div className={styles.note}>No actions are turned on. Choose them in Settings → Intelligence → HQ actions.</div>
      ) : (
        <>
          <div className={styles.presets} role="group" aria-label="Action presets">
            {presets.map((p) => (
              <button key={p.id} type="button" className={styles.preset} onClick={() => sel.applyPreset(p.actions)}>
                + {p.label}
              </button>
            ))}
            {sel.ticked.length > 0 && (
              <button type="button" className={styles.preset} onClick={sel.clear}>Clear</button>
            )}
          </div>
          {catalog.domains.map((d) => {
            const rows = sel.available.filter((a) => a.domain === d.id)
            if (!rows.length) return null
            return (
              <fieldset key={d.id} className={styles.group}>
                <legend className={styles.legend}>{d.label}</legend>
                {rows.map((a) => {
                  const on = sel.ticked.includes(a.name)
                  const blocked = !on && sel.atCap
                  return (
                    <label key={a.name} className={styles.row} data-blocked={blocked ? 'true' : 'false'}>
                      <input
                        type="checkbox"
                        className={styles.check}
                        checked={on}
                        onChange={() => { if (!blocked) sel.toggle(a.name) }}
                        {...(blocked ? { 'aria-disabled': 'true', 'aria-describedby': capId } : {})}
                      />
                      <span className={styles.name}>{a.label}</span>
                      <span className={styles.risk}>{a.risk.join(' · ')}</span>
                    </label>
                  )
                })}
              </fieldset>
            )
          })}
          <div id={capId} className={styles.capNote}>
            {sel.atCap
              ? `At the limit: ${MAX_HQ_ACTIONS} actions per question. Untick one to choose another.`
              : `Each proposal waits for your Run click. Up to ${MAX_HQ_ACTIONS} per question.`}
          </div>
          <div className={styles.count} role="status" aria-live="polite">
            {sel.enabledCount} of {MAX_HQ_ACTIONS} enabled
          </div>
        </>
      )}
    </div>
  )
}
