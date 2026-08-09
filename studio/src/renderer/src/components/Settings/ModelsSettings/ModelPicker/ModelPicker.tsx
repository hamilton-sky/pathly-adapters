import { useState } from 'react'
import { BoardSelect, type BoardSelectOption } from '../../../shared/BoardSelect/BoardSelect'
import type { PricingModel } from '../../../../store/commsApi'
import s from './ModelPicker.module.css'

const CUSTOM = '__custom__'

function priceHint(m: PricingModel): string {
  return `$${m.input}/$${m.output} per MTok`
}

interface Props {
  /** The chosen company's priced models (empty until pricing loads, or for an unpriced company). */
  models: PricingModel[]
  /** Current model; '' = the company's engine default. */
  value: string
  onChange: (model: string) => void
}

// Model chooser for one company: a dropdown of that provider's priced models (each with a
// $/MTok hint) plus "Engine default" and a "Custom model…" escape hatch that reveals a free-text
// input (model drift — a model newer than the pricing table). A stored value that isn't in the
// list is shown as custom so it always round-trips.
export function ModelPicker({ models, value, onChange }: Props): JSX.Element {
  // Sticky only via explicit user choice; otherwise derived (a non-listed value → custom once
  // pricing has loaded, so an async pricing load doesn't strand a known model in the text box).
  const [forceCustom, setForceCustom] = useState(false)
  const known = value === '' || models.some((m) => m.model === value)
  const showCustom = forceCustom || (value !== '' && models.length > 0 && !known)

  if (showCustom) {
    return (
      <div className={s.customRow}>
        <input
          className={s.customInput}
          type="text"
          value={value}
          placeholder="e.g. claude-opus-5"
          aria-label="Custom model name"
          onChange={(e) => onChange(e.target.value)}
        />
        <button
          type="button"
          className={s.link}
          onClick={() => {
            setForceCustom(false)
            onChange('')
          }}
        >
          Use list
        </button>
      </div>
    )
  }

  const options: BoardSelectOption[] = [
    { value: '', label: 'Engine default', hint: 'Let the CLI pick its own model' },
    ...models.map((m) => ({ value: m.model, label: m.model, hint: priceHint(m) })),
    { value: CUSTOM, label: 'Custom model…', hint: 'Type any model name' },
  ]

  return (
    <BoardSelect
      ariaLabel="Model"
      value={known ? value : ''}
      options={options}
      placeholder="Engine default"
      onChange={(v) => {
        if (v === CUSTOM) {
          setForceCustom(true)
          onChange('')
        } else {
          onChange(v)
        }
      }}
    />
  )
}
