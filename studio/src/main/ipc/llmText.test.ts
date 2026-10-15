import { describe, expect, it } from 'vitest'
import { stripThinkTags } from './llmText'

describe('stripThinkTags', () => {
  it('drops a stray closing tag the model wrote into its answer', () => {
    expect(stripThinkTags('It is waiting on the card below.</think>')).toBe('It is waiting on the card below.')
  })

  it('drops opening tags too, and leaves other text alone', () => {
    expect(stripThinkTags('<think>a <b>c</b>')).toBe('a <b>c</b>')
    expect(stripThinkTags('no tags')).toBe('no tags')
  })
})
