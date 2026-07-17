import React, { useState, useRef, useEffect } from 'react'
import { X } from 'lucide-react'
import { Tooltip } from '../../ui'
import { COMMENT_COLORS } from '../useComments'
import type { CommentColor } from '../useComments'
import { PromptActionConfig } from '../../shared/PromptActionConfig/PromptActionConfig'
import { useMergedPresets } from '../../shared/PromptActionConfig/useMergedPresets'
import { useProjectStore } from '../../../store/projectStore'
import { COMMENT_VERBS } from '../commentVerbs'
import { CommentAnchor } from './CommentAnchor'
import { useDraggable } from './hooks/useDraggable'
import {
  type EditorCli,
  CLI_KEY_COMMENT,
  PRESET_KEY_COMMENT,
  loadEditorCli,
  saveEditorCli,
  loadPreset,
  savePreset,
  cliLabel,
} from '../../MarkdownEditor/EditorHeader/editorCli'
import styles from './CommentModal.module.css'

interface Props {
  anchorText: string
  x: number
  y: number
  initialBody?: string
  onAdd: (body: string, color: CommentColor) => void
  onSendNow: (body: string, color: CommentColor, cli: EditorCli, verbName: string, extra: string) => void
  onDraftChange: (body: string) => void
  onClose: () => void
  onCancel: () => void
}

export function CommentModal({ anchorText, x, y, initialBody, onAdd, onSendNow, onDraftChange, onClose, onCancel }: Props): JSX.Element {
  const [body, setBody] = useState(initialBody ?? '')
  const [selectedColor, setSelectedColor] = useState<CommentColor>('yellow')
  const [cli, setCli] = useState<EditorCli>(() => loadEditorCli(CLI_KEY_COMMENT))
  const [verb, setVerb] = useState(() => loadPreset(PRESET_KEY_COMMENT))
  const canSubmit = body.trim().length > 0
  const ref = useRef<HTMLDivElement>(null)
  const { onHandleMouseDown } = useDraggable(ref)
  // Show the user's DB-backed 'comment' verbs alongside the built-ins in the ACTION dropdown.
  const projectRoot = useProjectStore((s) => s.projectPath)
  const { presets: mergedVerbs } = useMergedPresets(COMMENT_VERBS, {
    kind: 'preset',
    category: 'comment',
    projectRoot,
  })

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const { width, height } = el.getBoundingClientRect()
    let left = x - width / 2
    let top = y + 12
    left = Math.max(8, Math.min(left, window.innerWidth - width - 8))
    if (top + height > window.innerHeight - 8) top = y - height - 12
    el.style.setProperty('--modal-x', `${left}px`)
    el.style.setProperty('--modal-y', `${top}px`)
  }, [x, y])

  // Update accent color when selected swatch changes
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.setProperty('--modal-accent', `var(--comment-${selectedColor}-border)`)
  }, [selectedColor])

  useEffect(() => {
    function onMouseDown(e: MouseEvent): void {
      const t = e.target as Node
      // The ACTION dropdown portals its menu outside the card — clicks there must not close it.
      if (t instanceof Element && t.closest('[data-board-select-menu]')) return
      if (!ref.current?.contains(t)) onClose()
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => document.removeEventListener('mousedown', onMouseDown)
  }, [onClose])

  function handleCancel(): void {
    setSelectedColor('yellow')
    onCancel()
  }

  function handleCliChange(next: EditorCli): void {
    setCli(next)
    saveEditorCli(CLI_KEY_COMMENT, next)
  }

  function handleVerbChange(name: string): void {
    setVerb(name)
    savePreset(PRESET_KEY_COMMENT, name)
  }

  return (
    <div ref={ref} className={styles.modal} onMouseDown={(e) => e.stopPropagation()}>
      <div className={styles.header} onMouseDown={onHandleMouseDown}>
        <span className={styles.title}>Comment</span>
        <button type="button" className={styles.closeBtn} onClick={handleCancel} aria-label="Close">
          <X size={14} />
        </button>
      </div>

      {anchorText && <CommentAnchor text={anchorText} />}

      <div className={styles.swatchRow}>
        <span className={styles.srOnly}>Comment color</span>
        {COMMENT_COLORS.map((color) => (
          <Tooltip key={color} label={color.charAt(0).toUpperCase() + color.slice(1)} placement="top">
            <button
              type="button"
              className={`${styles.swatch} ${selectedColor === color ? styles.swatchSelected : ''}`}
              aria-label={`Set comment color to ${color}`}
              aria-pressed={selectedColor === color}
              onClick={() => setSelectedColor(color)}
              data-color={color}
            />
          </Tooltip>
        ))}
      </div>

      <textarea
        className={styles.textarea}
        placeholder="Describe the issue or suggestion…"
        value={body}
        onChange={(e) => { setBody(e.target.value); onDraftChange(e.target.value) }}
        rows={4}
        autoFocus
      />

      <PromptActionConfig
        heading=""
        presetLabel="ACTION"
        presets={mergedVerbs}
        selectedPreset={verb}
        promptText=""
        extra=""
        cli={cli}
        primaryLabel=""
        onSelectPreset={handleVerbChange}
        onPromptTextChange={() => { /* banner hidden */ }}
        onExtraChange={() => { /* extra-instructions box hidden */ }}
        onCliChange={handleCliChange}
        onReset={() => { /* footer hidden */ }}
        onPrimary={() => { /* footer hidden */ }}
        showExtra={false}
        showBanner={false}
        showFooter={false}
      />

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.sendBtn}
          disabled={!canSubmit}
          onClick={() => { if (canSubmit) onSendNow(body.trim(), selectedColor, cli, verb, '') }}
        >
          Send to {cliLabel(cli)}
        </button>
        <button
          type="button"
          className={styles.addBtn}
          disabled={!canSubmit}
          onClick={() => { if (canSubmit) onAdd(body.trim(), selectedColor) }}
        >
          Add comment
        </button>
      </div>
    </div>
  )
}
