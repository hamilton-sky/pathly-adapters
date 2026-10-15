import type { HqContextManifest } from '../../../../store/chatStore'
import { HQ_SECTIONS, isDefaultHqSections, useHqContextStore } from '../../../../store/hqContextStore'
import { formatTokens } from '../../ContextManifest/manifestUtils'
import { sectionTokens } from '../scopeUtils'
import styles from './ContextTab.module.css'

/** The board sections the next HQ question carries (saved choice). Each row
 *  shows the size it took on the latest answer, "—" when never measured. */
export function ContextTab({ manifest }: { manifest: HqContextManifest | null }): JSX.Element {
  const enabled = useHqContextStore((s) => s.enabled)
  const toggle = useHqContextStore((s) => s.toggle)
  const reset = useHqContextStore((s) => s.reset)

  return (
    <fieldset className={styles.fieldset}>
      <legend className={styles.legend}>Board sections for the next question</legend>
      <ul className={styles.list}>
        {HQ_SECTIONS.map((s) => {
          const size = sectionTokens(manifest, s.name)
          const last = manifest?.sections.find((x) => x.name === s.name)
          const wasCut = enabled[s.name] && last?.cut_reason === 'over budget'
          return (
            <li key={s.name}>
              <label className={styles.row}>
                <input
                  type="checkbox"
                  className={styles.check}
                  checked={enabled[s.name]}
                  onChange={() => toggle(s.name)}
                />
                <span className={styles.name}>{s.label}</span>
                <span className={styles.size}>{size === null ? '—' : `~${formatTokens(size)}`}</span>
              </label>
              {wasCut && <div className={styles.note}>Cut last time: over budget</div>}
            </li>
          )
        })}
      </ul>
      {!isDefaultHqSections(enabled) && (
        <button type="button" className={styles.reset} onClick={reset}>
          Reset to defaults
        </button>
      )}
    </fieldset>
  )
}
