import { MarkdownEditor } from '../../MarkdownEditor'
import styles from './DraftEditView.module.css'

interface Props {
  /** Current editor text — the reconstructed result, or the user's manual edit. */
  value: string
  onChange: (value: string) => void
  /** True once the user has typed here (so the buffer overrides accept toggles). */
  edited: boolean
  /** Drop the manual edit and follow the section accept/reject choices again. */
  onReset: () => void
}

/**
 * Final escape hatch: edit the reconstructed result directly before applying.
 * Seeded from the section accept/reject choices; once the user types, this
 * buffer becomes the source of truth on Apply (see DraftDiffViewer).
 */
export function DraftEditView({ value, onChange, edited, onReset }: Props) {
  return (
    <div className={styles.view}>
      <div className={styles.bar}>
        <span className={styles.note}>
          {edited
            ? 'Editing the result directly — accept/reject toggles are paused.'
            : 'The reconstructed result. Edit here to hand-tweak before applying.'}
        </span>
        <span className={styles.spacer} />
        <button type="button" className={styles.reset} disabled={!edited} onClick={onReset}>
          ↺ Reset to reconstructed
        </button>
      </div>
      <div className={styles.editor}>
        <MarkdownEditor value={value} onChange={onChange} />
      </div>
    </div>
  )
}
