import { marked } from 'marked'
import styles from './MarkdownPreview.module.css'

interface MarkdownPreviewProps {
  content: string
}

export function MarkdownPreview({ content }: MarkdownPreviewProps): JSX.Element {
  const html = marked(content) as string

  return (
    <div className={styles.previewWrapper}>
      <div
        className={styles.preview}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  )
}
