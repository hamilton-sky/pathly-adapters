import { describe, it, expect } from 'vitest'
import { featureFromPath } from './featureFromPath'

describe('featureFromPath', () => {
  it('extracts the slug from a feature-dir path (posix + windows separators)', () => {
    expect(featureFromPath('/home/u/proj/pathly/features/spawn-policy/SPEC.md')).toBe('spawn-policy')
    expect(featureFromPath('C:\\proj\\pathly\\features\\my-feat\\DOC.md')).toBe('my-feat')
  })

  it('returns undefined for a non-feature path or empty input', () => {
    expect(featureFromPath('/home/u/proj/README.md')).toBeUndefined()
    expect(featureFromPath('/home/u/proj/pathly/project/artifacts/x.md')).toBeUndefined()
    expect(featureFromPath('')).toBeUndefined()
    expect(featureFromPath(null)).toBeUndefined()
    expect(featureFromPath(undefined)).toBeUndefined()
  })
})
