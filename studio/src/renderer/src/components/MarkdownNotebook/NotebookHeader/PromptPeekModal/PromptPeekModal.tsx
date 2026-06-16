import React, { useEffect, useRef, useState } from 'react'
import { RotateCcw } from 'lucide-react'
import styles from './PromptPeekModal.module.css'

interface Props {
  title: string
  fileName: string
  defaultPrompt: string
  storageKey: string
  onClose: () => void
  onUseOnce: (prompt: string) => void
}

export default function PromptPeekModal({ title, fileName, defaultPrompt, storageKey, onClose, onUseOnce }: Props) {
  const [prompt, setPrompt] = useState(() => {
    try { return localStorage.getItem(storageKey) ?? defaultPrompt } catch { return defaultPrompt }
  })
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => { textareaRef.current?.focus() }, [])

  function handleReset() {
    setPrompt(defaultPrompt)
    try { localStorage.removeItem(storageKey) } catch {}
  }

  function handleSaveDefault() {
    try { localStorage.setItem(storageKey, prompt) } catch {}
    onClose()
  }

  function handleUseOnce() {
    onUseOnce(prompt)
    onClose()
  }

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.card} onClick={e => e.stopPropagation()}>
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <span className={styles.title}>{title}</span>
            <span className={styles.fileName}>{fileName}</span>
          </div>
          <button type="button" className={styles.resetBtn} onClick={handleReset} aria-label="Reset to default">
            <RotateCcw size={12} />
            Reset
          </button>
        </div>
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          spellCheck={false}
          rows={10}
        />
        <div className={styles.footer}>
          <button type="button" className={styles.cancelBtn} onClick={onClose}>Cancel</button>
          <button type="button" className={styles.useOnceBtn} onClick={handleUseOnce}>Use once</button>
          <button type="button" className={styles.saveBtn} onClick={handleSaveDefault}>Save default</button>
        </div>
      </div>
    </div>
  )
}
