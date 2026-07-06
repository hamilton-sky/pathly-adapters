import { Radio } from 'lucide-react'
import { BoardSelect, type BoardSelectOption } from '../BoardSelect/BoardSelect'
import s from './ProgressSelect.module.css'

// Board-updates verbosity — how chatty a headless agent is on the board. Shared by the
// Settings app-wide default and the per-run override in each run's guard modal.
const LEVELS: BoardSelectOption[] = [
  { value: 'quiet', label: 'Quiet — start + result only' },
  { value: 'normal', label: 'Normal — key steps' },
  { value: 'verbose', label: 'Verbose — every step' },
]
const INHERIT: BoardSelectOption = {
  value: '',
  label: 'Default (from Settings)',
  hint: 'Use the app-wide board-updates setting',
}

interface Props {
  /** Current value; '' = inherit the Settings default (only offered with allowInherit). */
  value: string
  onChange: (v: string) => void
  disabled?: boolean
  /** Prepend a "Default (from Settings)" option — for per-run overrides in guard modals. */
  allowInherit?: boolean
  /** Optional uppercase label above the select (omit in Settings, where a section title covers it). */
  label?: string
  /** Distinct id so multiple selects on screen don't collide on the label's htmlFor. */
  id?: string
}

export function ProgressSelect({
  value, onChange, disabled, allowInherit = false, label, id = 'board-updates-select',
}: Props): JSX.Element {
  const options = allowInherit ? [INHERIT, ...LEVELS] : LEVELS
  return (
    <div className={s.root}>
      {label && <label className={s.label} htmlFor={id}>{label}</label>}
      <BoardSelect
        id={id}
        ariaLabel="Board updates verbosity"
        value={value}
        options={options}
        onChange={onChange}
        leadingIcon={<Radio size={13} />}
        disabled={disabled}
      />
    </div>
  )
}
