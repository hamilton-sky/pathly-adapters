import React, { useState, useRef, useEffect } from 'react'
import { SlidersHorizontal } from 'lucide-react'
import { Tooltip } from '../../../ui'
import { PromptActionConfig } from '../../../shared/PromptActionConfig/PromptActionConfig'
import { COMMENT_VERBS } from '../../commentVerbs'
import {
  CLI_KEY_COMMENT,
  PRESET_KEY_COMMENT,
  loadEditorCli,
  saveEditorCli,
  loadPreset,
  savePreset,
  type EditorCli,
} from '../../../MarkdownEditor/EditorHeader/editorCli'
import styles from './CommentConfigButton.module.css'

interface Props {
  onCliChange: (cli: EditorCli) => void
  onPresetChange: (name: string) => void
}

export function CommentConfigButton({ onCliChange, onPresetChange }: Props): JSX.Element {
  const [open, setOpen] = useState(false)
  const [cli, setCli] = useState<EditorCli>(() => loadEditorCli(CLI_KEY_COMMENT))
  const [selectedPreset, setSelectedPreset] = useState(() => loadPreset(PRESET_KEY_COMMENT))
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onDown(e: MouseEvent): void {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
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
  }

  function handleReset(): void {
    handleCliChange('claude')
    handlePresetChange('')
  }

  return (
    <div className={styles.wrapper} ref={ref}>
      <Tooltip label="Comment defaults" placement="bottom">
        <button
          type="button"
          className={styles.trigger}
          onClick={() => setOpen((o) => !o)}
          aria-label="Configure comment defaults"
          {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        >
          <SlidersHorizontal size={15} />
        </button>
      </Tooltip>

      {open && (
        <div className={styles.popover} role="dialog" aria-label="Comment defaults">
          <PromptActionConfig
            heading="Comment defaults"
            presetLabel="ACTION"
            presets={COMMENT_VERBS}
            selectedPreset={selectedPreset}
            promptText=""
            extra=""
            cli={cli}
            primaryLabel="Done"
            onSelectPreset={handlePresetChange}
            onPromptTextChange={() => { /* presets have fixed prompts */ }}
            onExtraChange={() => { /* not used */ }}
            onCliChange={handleCliChange}
            onReset={handleReset}
            onPrimary={() => setOpen(false)}
            showExtra={false}
            bannerSlot={null}
          />
        </div>
      )}
    </div>
  )
}
