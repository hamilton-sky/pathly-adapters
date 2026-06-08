import React from 'react'
import { renderMarkdown } from '../../../utils/renderMarkdown'
import styles from './MarkdownRenderer.module.css'

interface Props {
  content: string
  className?: string
}

export default function MarkdownRenderer({ content, className }: Props) {
  return (
    <div
      className={`${styles.md} ${className ?? ''}`}
      dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
    />
  )
}
