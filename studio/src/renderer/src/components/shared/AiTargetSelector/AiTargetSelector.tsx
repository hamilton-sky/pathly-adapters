import { MODEL_CATALOG, BRIGHTSKY_ID } from '../../../services/modelManager'
import { ADAPTER_META } from '../../../services/cliEngine'
import { AI_SELECTION_OFF, isOff, type AiSelection } from '../../../services/aiRouter'
import s from './AiTargetSelector.module.css'

// One grouped <select> that emits an AiSelection (a local model or a CLI engine).
// Native <select>/<optgroup> is keyboard-native and accessible, and keeps this
// component well under the 150-line cap — DESIGN.md allows it over a custom
// listbox. Lives in shared/ so the Conv-3 ArtifactsView toolbar/per-artifact
// chips and HQ can all consume the same control.

const OFF_VALUE = 'off'

/** Encode an AiSelection as the <select> option value ('model:<id>' | 'engine:<id>' | 'off'). */
function encode(sel: AiSelection | null): string {
  if (!sel) return ''
  if (isOff(sel)) return OFF_VALUE
  return `${sel.type}:${sel.id}`
}

/** Parse a <select> value back into an AiSelection (or the Off sentinel). */
function decode(value: string): AiSelection {
  if (value === OFF_VALUE) return AI_SELECTION_OFF
  const [type, ...rest] = value.split(':')
  return { type: type === 'engine' ? 'engine' : 'model', id: rest.join(':') }
}

interface Props {
  value: AiSelection | null
  onChange: (sel: AiSelection) => void
  /** When true, adds an "Off" option that emits AI_SELECTION_OFF (consumers skip the run). */
  allowOff?: boolean
  id?: string
  ariaLabel?: string
  /** Disable the whole control (e.g. while a run is in flight). */
  disabled?: boolean
}

export function AiTargetSelector({
  value,
  onChange,
  allowOff = false,
  id,
  ariaLabel = 'AI target',
  disabled = false,
}: Props): JSX.Element {
  const current = encode(value)
  // Engines that have a headless one-shot mode (skip noHeadless ones per DESIGN.md).
  const engines = ADAPTER_META.filter((m) => !m.noHeadless)

  return (
    <div className={s.wrap} data-state={disabled ? 'loading' : 'ready'}>
      <select
        id={id}
        className={s.select}
        aria-label={ariaLabel}
        value={current}
        disabled={disabled}
        onChange={(e) => onChange(decode(e.target.value))}
      >
        {current === '' && (
          <option value="" disabled>
            Select AI target…
          </option>
        )}
        {allowOff && <option value={OFF_VALUE}>Off</option>}
        <optgroup label="Models">
          {MODEL_CATALOG.map((m) => (
            <option key={m.id} value={`model:${m.id}`}>
              {m.name}
            </option>
          ))}
          <option value={`model:${BRIGHTSKY_ID}`}>Brightsky</option>
        </optgroup>
        <optgroup label="CLI Engines">
          {engines.map((e) => (
            <option key={e.id} value={`engine:${e.id}`}>
              {e.label}
            </option>
          ))}
          {/* Headless-incapable engines listed disabled so the user sees why. */}
          {ADAPTER_META.filter((m) => m.noHeadless).map((e) => (
            <option key={e.id} value={`engine:${e.id}`} disabled>
              {e.label} (no headless)
            </option>
          ))}
        </optgroup>
      </select>
    </div>
  )
}
