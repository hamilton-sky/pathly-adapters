import React, { useEffect, useState } from 'react'
import { useUiStore } from '../../../store/uiStore'
import MarkdownRenderer from '../../shared/MarkdownRenderer/MarkdownRenderer'
import styles from './FilePreview.module.css'

export default function FilePreview() {
  const skillNotebookPath = useUiStore(s => s.skillNotebookPath)
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!skillNotebookPath) return
    setLoading(true)
    window.pathly.fs.read(skillNotebookPath)
      .then(text => { setContent(text ?? ''); setLoading(false) })
      .catch(() => setLoading(false))
  }, [skillNotebookPath])

  if (loading) return <div className={styles.loading}>Loading…</div>

  return (
    <div className={styles.root}>
      <MarkdownRenderer content={content} className={styles.content} />
    </div>
  )
}
