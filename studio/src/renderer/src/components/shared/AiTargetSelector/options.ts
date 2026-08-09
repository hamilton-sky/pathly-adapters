import { MODEL_CATALOG, BRIGHTSKY_ID } from '../../../services/modelManager'
import { ADAPTER_META } from '../../../services/cliEngine'
import { AI_SELECTION_OFF, isOff, type AiSelection } from '../../../services/aiRouter'

// Pure option model for AiTargetSelector — no React. Encodes/decodes the
// AiSelection ↔ option-value mapping ('model:<id>' | 'engine:<id>' | 'off') and
// builds the grouped Models / CLI-Engines rows the custom dropdown renders.

export const OFF_VALUE = 'off'

export interface AiOption {
  value: string
  label: string
  /** Present when the row is selectable but disabled — the greyed reason text. */
  disabledReason?: string
}

export interface AiOptionGroup {
  heading: string
  options: AiOption[]
}

/** Encode an AiSelection as an option value ('model:<id>' | 'engine:<id>' | 'off'). */
export function encode(sel: AiSelection | null): string {
  if (!sel) return ''
  if (isOff(sel)) return OFF_VALUE
  return `${sel.type}:${sel.id}`
}

/** Parse an option value back into an AiSelection (or the Off sentinel). */
export function decode(value: string): AiSelection {
  if (value === OFF_VALUE) return AI_SELECTION_OFF
  const [type, ...rest] = value.split(':')
  return { type: type === 'engine' ? 'engine' : 'model', id: rest.join(':') }
}

/** Build the grouped option model. `allowOff` prepends a single "Off" group.
 *  `preflight` (optional, keyed by adapter id) greys out engines that are not installed
 *  on this machine — without it every engine reads as usable and picking a missing one
 *  fails only at spawn time. Omitting it preserves the previous behavior exactly.
 *  `allowLocalModels` (default false) shows the local-model group. Local models are a SEPARATE
 *  system (chat uses them via modelStore); the summary target — the only user of this selector —
 *  is CLI-engine-only, so every summary spawn goes through the one gate (run_id + cost + policy).
 *  A caller opts into local models explicitly. */
export function buildGroups(
  allowOff: boolean,
  preflight?: Record<string, EnginePreflight>,
  allowLocalModels = false,
): AiOptionGroup[] {
  const groups: AiOptionGroup[] = []
  if (allowOff) {
    groups.push({ heading: '', options: [{ value: OFF_VALUE, label: 'Off' }] })
  }
  if (allowLocalModels) {
    groups.push({
      heading: 'Models',
      options: [
        ...MODEL_CATALOG.map((m) => ({ value: `model:${m.id}`, label: m.name })),
        { value: `model:${BRIGHTSKY_ID}`, label: 'Brightsky' },
      ],
    })
  }
  groups.push({
    heading: 'CLI Engines',
    options: ADAPTER_META.map((m) => {
      const row = preflight?.[m.id]
      const notInstalled = row && !row.available
        ? row.installHint ? `Not installed — ${row.installHint}` : 'Not installed'
        : undefined
      return {
        value: `engine:${m.id}`,
        label: m.label,
        // noHeadless engines are listed but greyed with their reason (DESIGN.md).
        // A missing binary wins over noHeadless — it is the more actionable blocker.
        disabledReason: notInstalled ?? m.noHeadless,
      }
    }),
  })
  return groups
}

/** Human-readable label for the currently-selected value (for the trigger). */
export function labelForValue(value: string, groups: AiOptionGroup[]): string {
  for (const g of groups) {
    const hit = g.options.find((o) => o.value === value)
    if (hit) return hit.label
  }
  return 'Select AI target…'
}
