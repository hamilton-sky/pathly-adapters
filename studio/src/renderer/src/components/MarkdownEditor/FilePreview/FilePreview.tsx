import React, { useEffect, useState } from 'react'
import { useUiStore } from '../../../store/uiStore'
import MarkdownRenderer from '../../shared/MarkdownRenderer/MarkdownRenderer'
import styles from './FilePreview.module.css'

export default function FilePreview() {
  const mdEditorPath = useUiStore(s => s.mdEditorPath)
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!mdEditorPath) return
    setLoading(true)
    window.pathly.fs.read(mdEditorPath)
      .then(text => { setContent(text ?? ''); setLoading(false) })
      .catch(() => setLoading(false))
  }, [mdEditorPath])

  if (loading) return <div className={styles.loading}>Loading…</div>

  return (
    <div className={styles.root}>
      <MarkdownRenderer content={content} className={styles.content} />
    </div>
  )
}
