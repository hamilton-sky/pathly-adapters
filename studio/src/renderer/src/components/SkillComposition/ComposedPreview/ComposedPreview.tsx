import type { ComposedSection } from '../../../services/skillComposition'
import { Spinner } from '../../ui'
import styles from './ComposedPreview.module.css'

interface Props {
  sections: ComposedSection[]
  tokens: number
  loading: boolean
}

/** Read-only render of the exact composed prompt — raw text, not markdown-rendered. */
export function ComposedPreview({ sections, tokens, loading }: Props): JSX.Element {
  return (
    <div className={styles.root}>
      <div className={styles.head}>
        <span className={styles.label}>Composed prompt preview</span>
        {loading && <Spinner size={12} />}
        <span className={styles.spacer} />
        <span className={styles.tokenCount}>≈ {tokens} tokens</span>
      </div>
      <div className={styles.body} data-loading={loading}>
        {sections.length === 0 && !loading && (
          <div className={styles.empty}>No fragments selected</div>
        )}
        {sections.map((s, i) => (
          <div key={`${s.heading}-${i}`} className={styles.section}>
            {s.heading && <div className={styles.sectionHeading}>{s.heading}</div>}
            <pre className={styles.sectionContent}>{s.content}</pre>
          </div>
        ))}
      </div>
    </div>
  )
}
