import { BoardSelect, type BoardSelectOption } from '../../../shared/BoardSelect/BoardSelect'
import { ADAPTER_META } from '../../../../services/cliEngine'
import type { ModelSel, PricingByProvider } from '../../../../store/commsApi'
import { ModelPicker } from '../ModelPicker/ModelPicker'
import s from './ModelRow.module.css'

// Headless-capable companies only — the model policy governs headless spawns (runner / board /
// editor one-shots); a non-headless engine (copilot) can't consume it. An adapter id doubles as
// its pricing-provider slug (claude/codex/antigravity), so pricing[sel.adapter] indexes directly.
const COMPANIES = ADAPTER_META.filter((m) => !m.noHeadless)

interface Props {
  /** Display name — "Global default" or a role/place (architect, split, …). */
  label: string
  /** Current selection, or null when this row inherits (role) / is unset (global). */
  sel: ModelSel | null
  pricing: PricingByProvider
  /** Empty-company option label: "Engine default (none)" (global) or "Inherit default" (role). */
  inheritLabel: string
  onSet: (adapter: string, model: string) => void
  onClear: () => void
}

// One model-policy row: a company picker plus — once a company is chosen — a model picker.
// Choosing the empty company option clears the row (→ inherit / unset); choosing a company
// creates the override and resets the model to that company's engine default.
export function ModelRow({ label, sel, pricing, inheritLabel, onSet, onClear }: Props): JSX.Element {
  const companyOptions: BoardSelectOption[] = [
    { value: '', label: inheritLabel },
    ...COMPANIES.map((c) => ({ value: c.id, label: c.label })),
  ]

  function onCompany(adapter: string): void {
    if (!adapter) onClear()
    else onSet(adapter, '')
  }

  return (
    <div className={s.row}>
      <span className={s.label}>{label}</span>
      <div className={s.controls}>
        <div className={s.company}>
          <BoardSelect
            ariaLabel={`Company for ${label}`}
            value={sel?.adapter ?? ''}
            options={companyOptions}
            onChange={onCompany}
            placeholder={inheritLabel}
          />
        </div>
        {sel && (
          <div className={s.model}>
            <ModelPicker
              models={pricing[sel.adapter] ?? []}
              value={sel.model}
              onChange={(model) => onSet(sel.adapter, model)}
            />
          </div>
        )}
      </div>
    </div>
  )
}
