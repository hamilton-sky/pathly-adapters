import { useState, useEffect, useRef } from 'react'
import { Edit2, Copy } from 'lucide-react'
import { marked } from 'marked'
import type { KeyboardEvent } from 'react'
import styles from './PromptPreview.module.css'

interface Props {
  prompt: string
  isModified: boolean
  label: string
}

export function PromptPreview({ prompt, isModified, label }: Props): JSX.Element {
  const [editing, setEditing]       = useState(false)
  const [customText, setCustomText] = useState<string | null>(null)
  const [copied, setCopied]         = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Reset manual edits when the assembled prompt changes (e.g. skill switch)
  useEffect(() => { setCustomText(null); setEditing(false) }, [prompt])

  const displayed    = customText ?? prompt
  const isHandEdited = customText !== null && customText.trim() !== prompt.trim()

  function toggleEdit(): void {
    if (!editing) {
      setCustomText((prev) => prev ?? prompt)
      setEditing(true)
      setTimeout(() => { textareaRef.current?.focus() }, 0)
    } else {
      setEditing(false)
    }
  }

  function handleCopy(): void {
    navigator.clipboard.writeText(displayed).catch(() => undefined)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>): void {
    if (e.key === 'Escape') setEditing(false)
  }

  const badgeText  = isHandEdited ? 'manually edited' : isModified ? 'modified from default' : null
  const badgeClass = `${styles.badge} ${isHandEdited ? styles.badgeHandEdited : styles.badgeModified}`
  const renderedHtml = renderMarkdown(displayed)

  return (
    <div className={styles.wrap}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.dot} />
          <span className={styles.headerLabel}>{label}</span>
          {badgeText && <span className={badgeClass}>{badgeText}</span>}
        </div>
        <div className={styles.headerRight}>
          <button
            type="button"
            className={`${styles.iconBtn} ${editing ? styles.iconBtnEditing : ''}`}
            onClick={toggleEdit}
            aria-label={editing ? 'Finish editing prompt' : 'Edit prompt inline'}
          >
            <Edit2 size={12} />
            <span>{editing ? 'done' : 'edit'}</span>
          </button>
          <button
            type="button"
            className={styles.iconBtn}
            onClick={handleCopy}
            aria-label="Copy prompt to clipboard"
          >
            <Copy size={12} />
            <span>{copied ? 'copied!' : 'copy'}</span>
          </button>
        </div>
      </div>
      {editing ? (
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          value={customText ?? prompt}
          onChange={(e) => setCustomText(e.target.value)}
          onKeyDown={handleKeyDown}
          spellCheck={false}
          aria-label="Edit prompt text"
        />
      ) : (
        // Content comes from trusted internal skill files — not user input
        // eslint-disable-next-line react/no-danger
        <div className={styles.preview} dangerouslySetInnerHTML={{ __html: renderedHtml }} />
      )}
    </div>
  )
}

function renderMarkdown(text: string): string {
  try {
    const result = marked.parse(text)
    return typeof result === 'string' ? result : String(result)
  } catch {
    return `<pre>${text.replace(/</g, '&lt;')}</pre>`
  }
}
