import { useState } from 'react'
import type { HqContextManifest, HqContextSection } from '../../../store/chatStore'
import { hqSectionLabel } from '../../../store/hqContextStore'
import { useHqComposerStore } from '../../../store/hqComposerStore'
import { formatTokens, sectionStatusLabel, usagePercent } from './manifestUtils'
import styles from './ContextManifest.module.css'

/** Amber note: board context could not be loaded. Never hidden. */
export function ContextUnavailableNote(): JSX.Element {
  return (
    <div className={styles.unavailable} role="note">
      <span className={styles.unavailableDot} aria-hidden="true" />
      <span>Board context unavailable — this answer was given without live board data.</span>
    </div>
  )
}

/** Collapsible manifest under an HQ answer: a read-only record of exactly the
 *  board packet the model was sent (from POST /hq/prompt). What the NEXT
 *  question carries is chosen in the composer's chip row; on the latest answer
 *  (`latest`) an "Adjust for next question" link opens it. */
export function ContextManifest({ manifest, latest = false }: { manifest: HqContextManifest; latest?: boolean }): JSX.Element {
  const [open, setOpen] = useState(false)
  const openScope = useHqComposerStore((s) => s.openScope)

  if (manifest.unavailable) {
    return <ContextUnavailableNote />
  }

  const includedCount = manifest.sections.filter((s) => s.included).length

  const row = (s: HqContextSection): JSX.Element => {
    const status = sectionStatusLabel(s)
    return (
      <li key={s.name} className={styles.section}>
        <span className={s.included ? styles.included : styles.cut} aria-hidden="true">
          {s.included ? '✓' : '–'}
        </span>
        <span className={styles.sectionName}>{hqSectionLabel(s.name)}</span>
        <span className={styles.sectionStatus}>{status}</span>
      </li>
    )
  }

  return (
    <div className={styles.wrap}>
      <button
        type="button"
        className={styles.toggle}
        onClick={() => setOpen((v) => !v)}
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
      >
        <span className={styles.caret} aria-hidden="true">{open ? '▾' : '▸'}</span>
        <span className={styles.label}>
          context · {manifest.board ? <span className={styles.board}>{manifest.board}</span> : null}
          {manifest.board ? ' · ' : ''}{formatTokens(manifest.tokens_est)}/{formatTokens(manifest.budget)} tokens
          {manifest.actions?.length ? ` · ${manifest.actions.length} action${manifest.actions.length === 1 ? '' : 's'}` : ''}
        </span>
        {!manifest.eligible_model && (
          <span className={styles.warn}>
            ⚠ {manifest.model || 'this model'} may be too small for this context
          </span>
        )}
      </button>
      {open && (
        <div className={styles.body}>
          <progress
            className={styles.bar}
            value={usagePercent(manifest.tokens_est, manifest.budget)}
            max={100}
            aria-label="Context tokens used of budget"
          />
          <ul className={styles.sections}>{manifest.sections.map(row)}</ul>
          <div className={styles.meta}>
            {includedCount}/{manifest.sections.length} sections used · model {manifest.model}
          </div>
          {latest && (
            <button type="button" className={styles.adjust} onClick={() => openScope('context')}>
              Adjust for next question
            </button>
          )}
        </div>
      )}
    </div>
  )
}
