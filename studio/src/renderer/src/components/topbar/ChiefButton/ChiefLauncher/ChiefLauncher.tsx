import { useMemo } from 'react'
import { PromptActionConfig } from '../../../shared/PromptActionConfig/PromptActionConfig'
import { OpenChiefCard } from '../OpenChiefCard/OpenChiefCard'
import { spendNote, tierSummary, toPromptPresets } from '../chiefLauncherUtils'
import { useChiefLauncher } from '../hooks/useChiefLauncher'
import s from './ChiefLauncher.module.css'

interface Props {
  projectRoot: string
  onOpened: () => void
}

/** The Chief launcher: engine + style (the server names its tier) → Open, or the open chief. */
export function ChiefLauncher({ projectRoot, onOpened }: Props): JSX.Element {
  const l = useChiefLauncher(projectRoot, onOpened)
  const options = useMemo(() => toPromptPresets(l.presets), [l.presets])

  if (l.session?.open) {
    return (
      <>
        <OpenChiefCard session={l.session} busy={l.busy} onShowTab={l.showTab} onClose={l.close} />
        {l.error && <div className={s.error} role="alert">{l.error}</div>}
      </>
    )
  }

  if (!l.list || !l.current) {
    return (
      <div className={s.loading} role={l.error ? 'alert' : undefined}>
        {l.error ?? 'Loading chief styles…'}
      </div>
    )
  }

  const spend = spendNote(l.current.tier, l.list.limits)
  const note = (
    <div className={s.note}>
      <strong>{tierSummary(l.current.tier)}</strong>
      {spend && <span className={s.spend}>{spend}</span>}
      {l.error && <span className={s.errorText} role="alert">{l.error}</span>}
    </div>
  )

  return (
    <PromptActionConfig
      heading="Chief"
      presetLabel="STYLE"
      presets={options}
      selectedPreset={l.current.name}
      promptText={l.promptText}
      extra=""
      cli={l.cli}
      running={l.busy}
      primaryLabel={l.busy ? 'Opening…' : 'Open chief'}
      onSelectPreset={l.selectPreset}
      onPromptTextChange={l.setPromptText}
      onExtraChange={() => undefined}
      onCliChange={l.changeCli}
      onReset={l.reset}
      onPrimary={() => void l.open()}
      onAddPreset={l.saveStyle}
      footerNote={note}
      showExtra={false}
    />
  )
}
