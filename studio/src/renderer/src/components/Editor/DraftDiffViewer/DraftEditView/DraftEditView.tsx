import { useRef } from 'react'
import { Replace } from 'lucide-react'
import { MarkdownEditor } from '../../MarkdownEditor'
import type { MarkdownEditorHandle } from '../../MarkdownEditor'
import { FindReplaceBar } from '../../FindReplaceBar/FindReplaceBar'
import { useFindReplace } from '../../useFindReplace'
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
  const editorRef = useRef<MarkdownEditorHandle>(null)
  const find = useFindReplace(editorRef, true, null)

  return (
    <div className={styles.view}>
      <div className={styles.bar}>
        <span className={styles.note}>
          {edited
            ? 'Editing the result directly — accept/reject toggles are paused.'
            : 'The reconstructed result. Edit here to hand-tweak before applying.'}
        </span>
        <span className={styles.spacer} />
        <button
          type="button"
          className={find.open ? styles.findToggleActive : styles.findToggle}
          onClick={() => find.toggle('find')}
          aria-label="Find and replace"
          title="Find & replace (Ctrl+F)"
          {...(find.open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        >
          <Replace size={14} />
        </button>
        <button type="button" className={styles.reset} disabled={!edited} onClick={onReset}>
          ↺ Reset to reconstructed
        </button>
      </div>
      {find.open && (
        <FindReplaceBar
          mode={find.mode}
          query={find.query}
          replaceText={find.replaceText}
          info={find.info}
          onQueryChange={find.onQueryChange}
          onReplaceChange={find.onReplaceChange}
          onNext={find.next}
          onPrev={find.prev}
          onReplaceOne={find.replaceOne}
          onReplaceAll={find.replaceAll}
          onClose={find.close}
        />
      )}
      <div className={styles.editor}>
        <MarkdownEditor ref={editorRef} value={value} onChange={onChange} />
      </div>
    </div>
  )
}
