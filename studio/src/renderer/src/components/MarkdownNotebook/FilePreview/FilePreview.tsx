import React, { useEffect, useState } from 'react'
import { useUiStore } from '../../../store/uiStore'
import MarkdownRenderer from '../../shared/MarkdownRenderer/MarkdownRenderer'
import styles from './FilePreview.module.css'

export default function FilePreview() {
  const notebookPath = useUiStore(s => s.notebookPath)
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!notebookPath) return
    setLoading(true)
    window.pathly.fs.read(notebookPath)
      .then(text => { setContent(text ?? ''); setLoading(false) })
      .catch(() => setLoading(false))
  }, [notebookPath])

  if (loading) return <div className={styles.loading}>Loading…</div>

  return (
    <div className={styles.root}>
      <MarkdownRenderer content={content} className={styles.content} />
    </div>
  )
}
