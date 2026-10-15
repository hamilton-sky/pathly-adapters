import { renderSafeMarkdown } from '../../lib/safeMarkdown'
import styles from './MarkdownPreview.module.css'

interface MarkdownPreviewProps {
  content: string
  /** Show http(s) images — the editor's own open file sets this; agent analyses don't. */
  images?: boolean
}

// Raw HTML is escaped even in the user's own file: files under pathly/ are mostly
// agent-written, and this renderer can reach window.pathly.
export function MarkdownPreview({ content, images = false }: MarkdownPreviewProps): JSX.Element {
  const html = renderSafeMarkdown(content, { breaks: false, images })

  return (
    <div className={styles.previewWrapper}>
      <div
        className={styles.preview}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  )
}
