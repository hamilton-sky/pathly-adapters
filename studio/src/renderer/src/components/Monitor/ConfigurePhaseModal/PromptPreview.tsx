import { useState, useEffect, useRef } from 'react'
import { Edit2, Copy } from 'lucide-react'
import { marked } from 'marked'
import type { KeyboardEvent } from 'react'
import styles from './PromptPreview.module.css'

interface Props {
  prompt: string
  agentPrompt?: string
  isModified: boolean
  label: string
}

type PromptView = 'skill' | 'agent'

export function PromptPreview({ prompt, agentPrompt, isModified, label }: Props): JSX.Element {
  const [promptView, setPromptView]       = useState<PromptView>('skill')
  const [editing, setEditing]             = useState(false)
  const [customSkill, setCustomSkill]     = useState<string | null>(null)
  const [customAgent, setCustomAgent]     = useState<string | null>(null)
  const [copied, setCopied]               = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Reset skill edits when assembled prompt changes (skill/agent/host switch)
  useEffect(() => { setCustomSkill(null); setEditing(false); setPromptView('skill') }, [prompt])
  // Reset agent edits when agent changes
  useEffect(() => { setCustomAgent(null); setEditing(false) }, [agentPrompt])

  const isAgentView  = promptView === 'agent'
  const displayed    = isAgentView
    ? (customAgent ?? agentPrompt ?? '')
    : (customSkill ?? prompt)
  const isHandEdited = isAgentView
    ? customAgent !== null && customAgent.trim() !== (agentPrompt ?? '').trim()
    : customSkill !== null && customSkill.trim() !== prompt.trim()

  function toggleEdit(): void {
    if (!editing) {
      if (isAgentView) setCustomAgent((prev) => prev ?? agentPrompt ?? '')
      else             setCustomSkill((prev) => prev ?? prompt)
      setEditing(true)
      setTimeout(() => { textareaRef.current?.focus() }, 0)
    } else {
      setEditing(false)
    }
  }

  function handleChange(value: string): void {
    if (isAgentView) setCustomAgent(value)
    else             setCustomSkill(value)
  }

  function handleCopy(): void {
    navigator.clipboard.writeText(displayed).catch(() => undefined)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>): void {
    if (e.key === 'Escape') setEditing(false)
  }

  function switchView(v: PromptView): void {
    setPromptView(v)
    setEditing(false)
  }

  const badgeText  = isHandEdited ? 'manually edited' : (!isAgentView && isModified) ? 'modified from default' : null
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
          {/* Skill / Agent toggle — fixed right, always visible */}
          <div className={styles.viewToggle}>
            <button
              type="button"
              className={`${styles.viewBtn} ${!isAgentView ? styles.viewBtnActive : ''}`}
              onClick={() => switchView('skill')}
            >skill</button>
            <button
              type="button"
              className={`${styles.viewBtn} ${isAgentView ? styles.viewBtnActive : ''}`}
              onClick={() => switchView('agent')}
              disabled={!agentPrompt}
            >agent</button>
          </div>

          <div className={styles.headerActions}>
            <button
              type="button"
              className={`${styles.iconBtn} ${editing ? styles.iconBtnEditing : ''}`}
              onClick={toggleEdit}
              aria-label={editing ? 'Finish editing' : `Edit ${isAgentView ? 'agent' : 'skill'} prompt inline`}
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

      </div>

      {editing ? (
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          value={displayed}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          spellCheck={false}
          aria-label={`Edit ${isAgentView ? 'agent' : 'skill'} prompt text`}
        />
      ) : (
        // Content comes from trusted internal skill/agent files — not user input
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
