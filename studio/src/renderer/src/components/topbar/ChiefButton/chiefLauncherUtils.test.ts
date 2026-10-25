import { describe, expect, it } from 'vitest'
import type { ChiefPreset } from '../../../services/chiefApi'
import {
  editedPrompt,
  isChiefEngine,
  spendNote,
  styleFileName,
  tierSummary,
  toPromptPresets,
  withTierLine,
} from './chiefLauncherUtils'

const operator: ChiefPreset = {
  name: 'operator',
  label: 'Operator',
  tier: 'operator',
  text: 'You are the chief.\n',
  source: 'builtin',
  scope: null,
}
const limits = { max_runs_per_session: 20, max_cost_usd_per_run: 10 }

describe('chiefLauncherUtils', () => {
  it('accepts only the engines POST /chief/open accepts', () => {
    expect(isChiefEngine('claude')).toBe(true)
    expect(isChiefEngine('codex')).toBe(true)
    expect(isChiefEngine('agy')).toBe(false)
  })

  it('words the tier the server reported', () => {
    expect(tierSummary('operator')).toMatch(/^Tier: Operator — .*starts and stops runs/)
    expect(tierSummary('status')).toMatch(/changes nothing/)
  })

  it('warns about spend only for the operator tier, with the server limits', () => {
    expect(spendNote('operator', limits)).toBe(
      'Can start up to 20 runs, each up to $10 — they cost money.',
    )
    expect(spendNote('planner', limits)).toBeNull()
  })

  it('sends a prompt only when the user edited the style', () => {
    expect(editedPrompt('You are the chief.', operator)).toBeUndefined()
    expect(editedPrompt('You are the chief. Be brief.', operator)).toBe(
      'You are the chief. Be brief.',
    )
  })

  it('keeps the tier shown when a style is saved, and leaves existing front matter alone', () => {
    expect(withTierLine('Body', 'operator')).toBe('---\ntier: operator\n---\nBody')
    const own = '---\ntier: planner\n---\nBody'
    expect(withTierLine(own, 'operator')).toBe(own)
  })

  it('makes a name the prompt library accepts', () => {
    expect(styleFileName('  My Night Shift! ')).toBe('my-night-shift')
    expect(styleFileName('***')).toBe('')
  })

  it('labels a user style with its tier and where it lives', () => {
    const [row] = toPromptPresets([{ ...operator, source: 'user', scope: 'project' }])
    expect(row.hint).toBe('Operator tier · your project style')
    expect(row.prompt).toBe(operator.text)
  })
})
