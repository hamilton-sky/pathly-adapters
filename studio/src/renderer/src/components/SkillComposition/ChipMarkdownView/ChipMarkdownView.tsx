import type { ComposedSection } from '../../../services/skillComposition'
import { Spinner } from '../../ui'
import MarkdownRenderer from '../../shared/MarkdownRenderer/MarkdownRenderer'
import styles from './ChipMarkdownView.module.css'

interface Props {
  title: string
  sections: ComposedSection[]
  loading: boolean
}

function estimateTokens(sections: ComposedSection[]): number {
  const words = sections.reduce((sum, s) => sum + s.content.split(/\s+/).filter(Boolean).length, 0)
  return Math.round(words * 1.3)
}

/** Renders the active chip's sections as stylish markdown — reuses the Markdown Editor's renderer. */
export function ChipMarkdownView({ title, sections, loading }: Props): JSX.Element {
  const tokens = estimateTokens(sections)

  return (
    <div className={styles.root}>
      <div className={styles.head}>
        <span className={styles.title}>{title}</span>
        {loading && <Spinner size={12} />}
        <span className={styles.spacer} />
        <span className={styles.tokenCount}>≈ {tokens} tokens</span>
      </div>
      <div className={styles.body} data-loading={loading}>
        {sections.length === 0 && !loading && <div className={styles.empty}>No content</div>}
        {sections.map((s, i) => (
          <div key={`${s.origin}-${s.heading}-${i}`} className={styles.section}>
            {s.heading && <div className={styles.sectionHeading}>{s.heading}</div>}
            <MarkdownRenderer content={s.content} className={styles.sectionContent} />
          </div>
        ))}
      </div>
    </div>
  )
}
