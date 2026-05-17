import { marked } from 'marked'
import { useTheme } from '../../useTheme'

interface MarkdownPreviewProps {
  content: string
}

export function MarkdownPreview({ content }: MarkdownPreviewProps): JSX.Element {
  const t = useTheme()
  const html = marked(content) as string

  return (
    <div
      style={{
        maxWidth: '720px',
        margin: '0 auto',
        padding: '24px',
        color: t.textPrimary,
        fontFamily: 'system-ui, -apple-system, sans-serif',
        fontSize: '15px',
        lineHeight: '1.7',
        overflowY: 'auto',
        height: '100%'
      }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
