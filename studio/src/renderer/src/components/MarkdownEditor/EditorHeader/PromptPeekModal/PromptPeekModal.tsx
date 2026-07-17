import React, { useState } from 'react'
import { PromptActionConfig } from '../../../shared/PromptActionConfig/PromptActionConfig'
import { resolvePrompt, type PromptPreset } from '../../../shared/PromptActionConfig/presetTypes'
import { useMergedPresets, type PromptLibraryRef } from '../../../shared/PromptActionConfig/useMergedPresets'
import { type EditorCli, savePreset } from '../editorCli'
import styles from './PromptPeekModal.module.css'

interface Props {
  title: string
  fileName: string
  /** Resolved file path (with forward slashes) used for {{FILE}} substitution. */
  filePath: string
  storageKey: string
  presets: PromptPreset[]
  /** When set, merges the user's DB-backed library prompts into the dropdown + enables "＋ Save". */
  library?: PromptLibraryRef
  selectedPreset: string
  presetPersistKey: string
  cli: EditorCli
  onCliChange: (cli: EditorCli) => void
  onClose: () => void
  onUseOnce: (prompt: string) => void
  onPresetChange: (name: string) => void
}

export default function PromptPeekModal({
  title,
  fileName,
  filePath,
  storageKey,
  presets,
  library,
  selectedPreset,
  presetPersistKey,
  cli,
  onCliChange,
  onClose,
  onUseOnce,
  onPresetChange,
}: Props) {
  const norm = filePath.replace(/\\/g, '/')
  const [extra, setExtra] = useState('')
  // Merge the built-in presets with the user's DB-backed library prompts; the merged
  // array drives BOTH the dropdown and selection resolution (spawn uses the editable text).
  const { presets: mergedPresets, addPreset } = useMergedPresets(presets, library)

  // Migration: if a legacy override exists in localStorage, load it as the editable text
  // for the current preset so it is never silently discarded.
  const [prompt, setPrompt] = useState<string>(() => {
    try {
      const legacy = localStorage.getItem(storageKey)
      if (legacy) return legacy
      const preset = presets.find((p) => p.name === selectedPreset) ?? presets[0]
      return resolvePrompt(preset.prompt, { FILE: norm })
    } catch {
      const preset = presets.find((p) => p.name === selectedPreset) ?? presets[0]
      return resolvePrompt(preset.prompt, { FILE: norm })
    }
  })

  function handleSelectPreset(name: string) {
    const preset = mergedPresets.find((p) => p.name === name) ?? mergedPresets[0]
    const resolved = resolvePrompt(preset.prompt, { FILE: norm })
    setPrompt(resolved)
    savePreset(presetPersistKey, name)
    onPresetChange(name)
  }

  function handleReset() {
    const defaultPreset = presets[0]
    const resolved = resolvePrompt(defaultPreset.prompt, { FILE: norm })
    setPrompt(resolved)
    savePreset(presetPersistKey, defaultPreset.name)
    onPresetChange(defaultPreset.name)
    try { localStorage.removeItem(storageKey) } catch { /* ignore */ }
  }

  function handleSaveDefault() {
    try { localStorage.setItem(storageKey, prompt) } catch { /* ignore */ }
    savePreset(presetPersistKey, selectedPreset)
    onClose()
  }

  function handleUseOnce() {
    const eff = extra.trim()
      ? `${prompt}\n\n--- ADDITIONAL INSTRUCTIONS ---\n${extra.trim()}`
      : prompt
    onUseOnce(eff)
    onClose()
  }

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.card} onClick={(e) => e.stopPropagation()}>
        <div className={styles.caption}>
          <span className={styles.title}>{title}</span>
          <span className={styles.fileName}>{fileName}</span>
        </div>
        <PromptActionConfig
          heading=""
          presetLabel="PRESET"
          presets={mergedPresets}
          selectedPreset={selectedPreset}
          promptText={prompt}
          extra={extra}
          cli={cli}
          primaryLabel="Use once"
          secondaryLabel="Save default"
          onSelectPreset={handleSelectPreset}
          onPromptTextChange={setPrompt}
          onExtraChange={setExtra}
          onCliChange={onCliChange}
          onReset={handleReset}
          onPrimary={handleUseOnce}
          onSecondary={handleSaveDefault}
          onAddPreset={library ? (name) => addPreset(name, prompt) : undefined}
        />
      </div>
    </div>
  )
}
