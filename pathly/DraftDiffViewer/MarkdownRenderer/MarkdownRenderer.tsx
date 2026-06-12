import React from 'react'
import styles from './MarkdownRenderer.module.css'

interface Props {
  content: string
}

/* Minimal markdown renderer for the Result tab — headings, bold, inline code,
   ordered/unordered lists, paragraphs. Self-contained so the feature renders
   standalone; in the Studio app you can point DraftPreviewPanel at the shared
   MarkdownRenderer instead. */

function renderInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = []
  const re = /(`[^`]+`|\*\*[^*]+\*\*)/g
  let last = 0
  let key = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index))
    const tok = m[0]
    if (tok.startsWith('`')) parts.push(<code key={key++} className={styles.code}>{tok.slice(1, -1)}</code>)
    else parts.push(<strong key={key++}>{tok.slice(2, -2)}</strong>)
    last = m.index + tok.length
  }
  if (last < text.length) parts.push(text.slice(last))
  return parts
}

export default function MarkdownRenderer({ content }: Props) {
  const blocks = content.split(/\n\n+/)
  return (
    <div className={styles.md}>
      {blocks.map((block, i) => {
        if (block.startsWith('## ')) return <h2 key={i}>{renderInline(block.slice(3))}</h2>
        if (block.startsWith('# ')) return <h1 key={i}>{renderInline(block.slice(2))}</h1>
        const lines = block.split('\n')
        if (lines.length > 0 && lines.every((l) => /^\d+\.\s/.test(l))) {
          return <ol key={i}>{lines.map((l, j) => <li key={j}>{renderInline(l.replace(/^\d+\.\s/, ''))}</li>)}</ol>
        }
        if (lines.length > 0 && lines.every((l) => /^[-*]\s/.test(l))) {
          return <ul key={i}>{lines.map((l, j) => <li key={j}>{renderInline(l.replace(/^[-*]\s/, ''))}</li>)}</ul>
        }
        return <p key={i}>{renderInline(block)}</p>
      })}
    </div>
  )
}
