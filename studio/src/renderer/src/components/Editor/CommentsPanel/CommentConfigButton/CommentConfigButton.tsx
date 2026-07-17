import React, { useState, useRef, useEffect, useLayoutEffect } from 'react'
import { createPortal } from 'react-dom'
import { SlidersHorizontal } from 'lucide-react'
import { Tooltip } from '../../../ui'
import { PromptActionConfig } from '../../../shared/PromptActionConfig/PromptActionConfig'
import { useMergedPresets } from '../../../shared/PromptActionConfig/useMergedPresets'
import { useProjectStore } from '../../../../store/projectStore'
import { COMMENT_VERBS } from '../../commentVerbs'
import {
  CLI_KEY_COMMENT,
  PRESET_KEY_COMMENT,
  COMMENT_EXTRA_KEY,
  COMMENT_PROMPT_KEY,
  loadEditorCli,
  saveEditorCli,
  loadPreset,
  savePreset,
  type EditorCli,
} from '../../../MarkdownEditor/EditorHeader/editorCli'
import styles from './CommentConfigButton.module.css'

const POPOVER_WIDTH = 290

interface Props {
  onCliChange: (cli: EditorCli) => void
  onPresetChange: (name: string) => void
}

export function CommentConfigButton({ onCliChange, onPresetChange }: Props): JSX.Element {
  const [open, setOpen] = useState(false)
  const [cli, setCli] = useState<EditorCli>(() => loadEditorCli(CLI_KEY_COMMENT))
  const [selectedPreset, setSelectedPreset] = useState(() => loadPreset(PRESET_KEY_COMMENT))
  const [promptText, setPromptText] = useState(() => {
    const saved = loadPreset(COMMENT_PROMPT_KEY)
    if (saved) return saved
    return COMMENT_VERBS.find((v) => v.name === loadPreset(PRESET_KEY_COMMENT))?.prompt ?? ''
  })
  const [extra, setExtra] = useState(() => loadPreset(COMMENT_EXTRA_KEY))

  // Merge the built-in comment verbs with the user's DB-backed 'comment' library prompts;
  // the merged array drives BOTH the dropdown and preset→prompt resolution.
  const projectRoot = useProjectStore((st) => st.projectPath)
  const { presets: mergedVerbs, addPreset } = useMergedPresets(COMMENT_VERBS, {
    kind: 'preset',
    category: 'comment',
    projectRoot,
  })

  const triggerRef = useRef<HTMLButtonElement>(null)
  const popRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState({ top: 0, left: 0 })

  // Position below the trigger, right-aligned (opens leftward into the editor so the
  // narrow comments panel never clips it). Portaled to <body> to escape overflow:hidden.
  useLayoutEffect(() => {
    if (!open || !triggerRef.current) return
    const r = triggerRef.current.getBoundingClientRect()
    let left = r.right - POPOVER_WIDTH
    if (left < 8) left = 8
    setPos({ top: r.bottom + 6, left })
  }, [open])

  useEffect(() => {
    if (!open) return
    function onDown(e: MouseEvent): void {
      const t = e.target as Node
      // BoardSelect portals its menu outside the popover — clicks there must not close.
      if (t instanceof Element && t.closest('[data-board-select-menu]')) return
      if (popRef.current?.contains(t) || triggerRef.current?.contains(t)) return
      setOpen(false)
    }
    function onKey(e: KeyboardEvent): void {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  function handleCliChange(next: EditorCli): void {
    setCli(next)
    saveEditorCli(CLI_KEY_COMMENT, next)
    onCliChange(next)
  }

  function handlePresetChange(name: string): void {
    setSelectedPreset(name)
    savePreset(PRESET_KEY_COMMENT, name)
    onPresetChange(name)
    const next = mergedVerbs.find((v) => v.name === name)?.prompt ?? ''
    setPromptText(next)
    savePreset(COMMENT_PROMPT_KEY, next)
  }

  function handlePromptChange(v: string): void {
    setPromptText(v)
    savePreset(COMMENT_PROMPT_KEY, v)
  }

  function handleExtraChange(v: string): void {
    setExtra(v)
    savePreset(COMMENT_EXTRA_KEY, v)
  }

  function handleReset(): void {
    handleCliChange('claude')
    handlePresetChange('')
    handleExtraChange('')
  }

  return (
    <div className={styles.wrapper}>
      <Tooltip label="Comment defaults" placement="bottom">
        <button
          ref={triggerRef}
          type="button"
          className={styles.trigger}
          onClick={() => setOpen((o) => !o)}
          aria-label="Configure comment defaults"
          {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        >
          <SlidersHorizontal size={15} />
        </button>
      </Tooltip>

      {open &&
        createPortal(
          <div
            ref={popRef}
            className={styles.popover}
            style={{ '--pop-top': `${pos.top}px`, '--pop-left': `${pos.left}px` } as React.CSSProperties}
            role="dialog"
            aria-label="Comment defaults"
          >
            <PromptActionConfig
              heading="Comment defaults"
              presetLabel="ACTION"
              presets={mergedVerbs}
              selectedPreset={selectedPreset}
              promptText={promptText}
              extra={extra}
              cli={cli}
              primaryLabel="Done"
              onSelectPreset={handlePresetChange}
              onPromptTextChange={handlePromptChange}
              onExtraChange={handleExtraChange}
              onCliChange={handleCliChange}
              onReset={handleReset}
              onPrimary={() => setOpen(false)}
              onAddPreset={(name) => addPreset(name, promptText)}
            />
          </div>,
          document.body,
        )}
    </div>
  )
}
