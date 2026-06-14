import { useState, useEffect, useRef } from 'react'
import { Edit2, Copy } from 'lucide-react'
import { marked } from 'marked'
import { SegmentedControl } from '../SegmentedControl/SegmentedControl'
import { IconButton } from '../IconButton/IconButton'
import styles from './PromptPreview.module.css'

type PromptView = 'skill' | 'agent'

interface PromptPreviewProps {
  /** Header caption, e.g. `fix/build · builder · Claude Code`. */
  label: string
  /** Markdown source for the assembled skill prompt. */
  skillPrompt: string
  /** Markdown source for the agent prompt (enables the agent tab). */
  agentPrompt?: string
  /** Shows a “modified from default” badge on the skill view. */
  isModified?: boolean
}

/** Prompt preview card: skill/agent toggle, inline edit, copy, markdown body. */
export function PromptPreview({
  label,
  skillPrompt,
  agentPrompt,
  isModified = false,
}: PromptPreviewProps): JSX.Element {
  const [view, setView] = useState<PromptView>('skill')
  const [editing, setEditing] = useState(false)
  const [draftSkill, setDraftSkill] = useState<string | null>(null)
  const [draftAgent, setDraftAgent] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Reset local edits when the upstream prompts change.
  useEffect(() => {
    setDraftSkill(null)
    setEditing(false)
    setView('skill')
  }, [skillPrompt])
  useEffect(() => {
    setDraftAgent(null)
  }, [agentPrompt])

  const isAgent = view === 'agent'
  const text = isAgent ? draftAgent ?? agentPrompt ?? '' : draftSkill ?? skillPrompt
  const handEdited = isAgent
    ? draftAgent !== null && draftAgent.trim() !== (agentPrompt ?? '').trim()
    : draftSkill !== null && draftSkill.trim() !== skillPrompt.trim()

  function toggleEdit(): void {
    if (!editing) {
      if (isAgent) setDraftAgent((prev) => prev ?? agentPrompt ?? '')
      else setDraftSkill((prev) => prev ?? skillPrompt)
      setEditing(true)
      setTimeout(() => textareaRef.current?.focus(), 0)
    } else {
      setEditing(false)
    }
  }

  function handleChange(value: string): void {
    if (isAgent) setDraftAgent(value)
    else setDraftSkill(value)
  }

  function handleCopy(): void {
    navigator.clipboard.writeText(text).catch(() => undefined)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const badge = handEdited
    ? 'manually edited'
    : isModified && !isAgent
      ? 'modified from default'
      : null

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <span className={styles.dot} />
        <span className={styles.label}>{label}</span>
        {badge && (
          <span className={`${styles.badge} ${handEdited ? styles.badgeEdited : styles.badgeModified}`}>
            {badge}
          </span>
        )}

        <span className={styles.right}>
          <SegmentedControl<PromptView>
            size="sm"
            value={view}
            onChange={(next) => {
              setView(next)
              setEditing(false)
            }}
            options={[
              { value: 'skill', label: 'skill' },
              { value: 'agent', label: 'agent', disabled: !agentPrompt },
            ]}
          />
          <span className={styles.actions}>
            <IconButton
              icon={<Edit2 size={12} />}
              active={editing}
              onClick={toggleEdit}
              aria-label={editing ? 'Finish editing' : 'Edit prompt'}
            >
              {editing ? 'done' : 'edit'}
            </IconButton>
            <IconButton icon={<Copy size={12} />} onClick={handleCopy} aria-label="Copy prompt">
              {copied ? 'copied!' : 'copy'}
            </IconButton>
          </span>
        </span>
      </div>

      {editing ? (
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          value={text}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setEditing(false)
          }}
          spellCheck={false}
          aria-label="Edit prompt text"
        />
      ) : (
        // Content is trusted internal skill/agent markdown — not user input.
        // eslint-disable-next-line react/no-danger
        <div className={styles.body} dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }} />
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
