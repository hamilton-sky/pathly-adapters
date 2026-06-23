import s from './PromptActionConfig.module.css'

interface Props {
  resetLabel?: string
  primaryLabel: string
  secondaryLabel?: string
  running?: boolean
  onReset: () => void
  onPrimary: () => void
  onSecondary?: () => void
}

export function ConfigFooter({
  resetLabel = 'Reset',
  primaryLabel,
  secondaryLabel,
  running,
  onReset,
  onPrimary,
  onSecondary,
}: Props): JSX.Element {
  return (
    <footer className={s.footer}>
      <button type="button" className={s.resetBtn} onClick={onReset}>
        {resetLabel}
      </button>
      <span className={s.spacer} />
      {secondaryLabel && onSecondary && (
        <button type="button" className={s.secondaryBtn} onClick={onSecondary}>
          {secondaryLabel}
        </button>
      )}
      <button type="button" className={s.primaryBtn} disabled={running} onClick={onPrimary}>
        {primaryLabel}
      </button>
    </footer>
  )
}
