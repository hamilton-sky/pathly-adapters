// Pure helpers for the Chief launcher. The server decides a chief's tier from the preset name;
// these only word what it reported and shape the open request.
import type { ChiefPreset, ChiefPresetList, ChiefTier } from '../../../services/chiefApi'
import type { PromptPreset } from '../../shared/PromptActionConfig/presetTypes'

export const CLI_KEY_CHIEF = 'pathly.chief.cli'
export const PRESET_KEY_CHIEF = 'pathly.chief.preset'
export const DEFAULT_CHIEF_PRESET = 'status'

/** The engines `POST /chief/open` accepts. */
export const CHIEF_ENGINES = ['claude', 'codex'] as const

export function isChiefEngine(cli: string): boolean {
  return (CHIEF_ENGINES as readonly string[]).includes(cli)
}

const TIER_WORDS: Record<ChiefTier, string> = {
  status: 'reads the board, goals and runs, and changes nothing',
  planner: 'also posts notes and writes goals and tasks',
  operator: 'also starts and stops runs, answers agents and gives standing orders',
}

export function tierLabel(tier: ChiefTier): string {
  return tier.charAt(0).toUpperCase() + tier.slice(1)
}

/** "Tier: Operator — also starts and stops runs, …" */
export function tierSummary(tier: ChiefTier): string {
  return `Tier: ${tierLabel(tier)} — ${TIER_WORDS[tier] ?? TIER_WORDS.status}`
}

/** The spend line for a tier that can start runs, else null. */
export function spendNote(tier: ChiefTier, limits: ChiefPresetList['limits']): string | null {
  if (tier !== 'operator') return null
  const cost = limits.max_cost_usd_per_run
  return `Can start up to ${limits.max_runs_per_session} runs, each up to $${cost} — they cost money.`
}

/** The launcher's dropdown rows. A user style says where it lives in its hint. */
export function toPromptPresets(presets: ChiefPreset[]): PromptPreset[] {
  return presets.map((p) => ({
    name: p.name,
    label: p.label,
    hint: `${tierLabel(p.tier)} tier${p.source === 'user' ? ` · your ${p.scope ?? ''} style` : ''}`,
    prompt: p.text,
  }))
}

/** The `prompt` to send: the edited text, or undefined when it still matches the preset. */
export function editedPrompt(text: string, preset: ChiefPreset | undefined): string | undefined {
  if (!preset) return text.trim() ? text : undefined
  return text.trim() === preset.text.trim() ? undefined : text
}

/** A file name the prompt library accepts (letters, digits, `-`, `_`), or '' when none is left. */
export function styleFileName(name: string): string {
  return name.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '')
}

/** A saved style must name its tier, or the server opens it as Status. Keep the one shown. */
export function withTierLine(text: string, tier: ChiefTier): string {
  if (text.startsWith('---\n')) return text
  return `---\ntier: ${tier}\n---\n${text}`
}
