import React from 'react'
import { renderSafeMarkdown } from '../../../lib/safeMarkdown'
import styles from './MarkdownRenderer.module.css'

interface Props {
  content: string
  className?: string
  /** Show http(s) images — only when `content` is the user's own document. */
  images?: boolean
}

// Board cards, artifacts, goals, tasks and prompts all render here, and that text is
// written by agents or anyone who can post: escaped through renderSafeMarkdown, never
// plain marked(). `breaks: false` keeps marked's default line handling.
export default function MarkdownRenderer({ content, className, images = false }: Props) {
  return (
    <div
      className={`${styles.md} ${className ?? ''}`}
      dangerouslySetInnerHTML={{ __html: renderSafeMarkdown(content, { breaks: false, images }) }}
    />
  )
}
