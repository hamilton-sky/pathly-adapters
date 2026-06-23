import type { ReactNode } from 'react'
import { Sparkles } from 'lucide-react'
import CliSelect from '../../MarkdownEditor/EditorHeader/CliSelect/CliSelect'
import { type EditorCli } from '../../MarkdownEditor/EditorHeader/editorCli'
import { BoardSelect } from '../BoardSelect/BoardSelect'
import { PromptBanner } from '../PromptPreview/PromptPreview'
import { ConfigFooter } from './ConfigFooter'
import type { PromptPreset } from './presetTypes'
import s from './PromptActionConfig.module.css'

interface Props {
  heading: string
  presetLabel?: string
  presets: PromptPreset[]
  selectedPreset: string
  promptText: string
  extra: string
  cli: EditorCli
  running?: boolean
  primaryLabel: string
  onSelectPreset: (name: string) => void
  onPromptTextChange: (v: string) => void
  onExtraChange: (v: string) => void
  onCliChange: (cli: EditorCli) => void
  onReset: () => void
  onPrimary: () => void
  bannerSlot?: ReactNode
  footerNote?: ReactNode
  secondaryLabel?: string
  onSecondary?: () => void
  showExtra?: boolean
}

const PRESET_OPTIONS = (presets: PromptPreset[]) =>
  presets.map((p) => ({ value: p.name, label: p.label, hint: p.hint }))

export function PromptActionConfig({
  heading,
  presetLabel = 'PRESET',
  presets,
  selectedPreset,
  promptText,
  extra,
  cli,
  running,
  primaryLabel,
  onSelectPreset,
  onPromptTextChange,
  onExtraChange,
  onCliChange,
  onReset,
  onPrimary,
  bannerSlot,
  footerNote,
  secondaryLabel,
  onSecondary,
  showExtra = true,
}: Props): JSX.Element {
  return (
    <>
      <div className={s.heading}>{heading}</div>

      <section className={s.section}>
        <label className={s.sectionLabel} htmlFor="pac-preset">{presetLabel}</label>
        <BoardSelect
          id="pac-preset"
          ariaLabel={presetLabel}
          value={selectedPreset}
          options={PRESET_OPTIONS(presets)}
          onChange={onSelectPreset}
          leadingIcon={<Sparkles size={13} />}
        />
        {bannerSlot ?? (
          <PromptBanner editable editValue={promptText} onEditChange={onPromptTextChange} />
        )}
      </section>

      {showExtra !== false && (
        <section className={s.section}>
          <label className={s.sectionLabel} htmlFor="pac-extra">
            EXTRA INSTRUCTIONS <span className={s.optional}>· optional</span>
          </label>
          <textarea
            id="pac-extra"
            className={s.textarea}
            rows={3}
            placeholder="Any extra context or instructions for this run…"
            value={extra}
            onChange={(e) => onExtraChange(e.currentTarget.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); onPrimary() }
            }}
          />
        </section>
      )}

      <section className={s.section}>
        <span className={s.sectionLabel}>ENGINE</span>
        <CliSelect value={cli} onChange={onCliChange} align="right" up />
      </section>

      {footerNote && <div className={s.redirect}>{footerNote}</div>}

      <ConfigFooter
        primaryLabel={primaryLabel}
        secondaryLabel={secondaryLabel}
        running={running}
        onReset={onReset}
        onPrimary={onPrimary}
        onSecondary={onSecondary}
      />
    </>
  )
}
