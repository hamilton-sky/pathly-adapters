import { marked } from 'marked'

interface MarkdownPreviewProps {
  content: string
}

export function MarkdownPreview({ content }: MarkdownPreviewProps): JSX.Element {
  const html = marked(content) as string

  return (
    <div
      style={previewStyles.container}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}

const previewStyles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: '720px',
    margin: '0 auto',
    padding: '24px',
    color: '#cdd6f4',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    fontSize: '15px',
    lineHeight: '1.7',
    overflowY: 'auto',
    height: '100%'
  }
}
