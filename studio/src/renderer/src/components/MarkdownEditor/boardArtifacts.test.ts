import { describe, it, expect } from 'vitest'
import { boardTargetForFile } from './boardArtifacts'
import { buildBoardTargets } from './boardTargets'

// Drag-an-artifact-to-the-board resolution: boardTargetForFile derives WHICH board a dropped
// file belongs to from its path; buildBoardTargets uses it to hoist the suggested board.
// Regression guard for the plans/ -> features/ fix — before it, a flat features/ artifact
// matched nothing and silently fell back to the Global board.

describe('boardTargetForFile', () => {
  it('resolves the feature board for a flat pathly/features/ artifact', () => {
    expect(boardTargetForFile('C:/proj/pathly/features/my-feature/APPROACH.md')).toEqual({
      feature: 'my-feature',
      board: 'feature',
      scope: 'my-feature',
    })
  })

  it('still resolves legacy pathly/plans/ artifacts', () => {
    expect(boardTargetForFile('C:/proj/pathly/plans/legacy-feat/X.md')).toEqual({
      feature: 'legacy-feat',
      board: 'feature',
      scope: 'legacy-feat',
    })
  })

  it('maps a nested board-run artifact to its feature board (first segment after features/)', () => {
    const t = boardTargetForFile('C:/proj/pathly/features/my-feature/explorations/slug/TRACE.md')
    expect(t.scope).toBe('my-feature')
    expect(t.board).toBe('feature')
  })

  it('normalizes Windows backslashes', () => {
    expect(boardTargetForFile('C:\\proj\\pathly\\features\\my-feature\\SPEC.md').feature).toBe(
      'my-feature',
    )
  })

  it('falls back to the global board for a non-feature path', () => {
    expect(boardTargetForFile('C:/proj/README.md')).toEqual({
      feature: 'global',
      board: 'global',
      scope: 'global',
    })
  })
})

describe('buildBoardTargets', () => {
  it('hoists the path-derived feature board to the top, marked suggested', () => {
    const opts = buildBoardTargets(
      'C:/proj/pathly/features/beta/X.md',
      ['alpha', 'beta'],
      'C:/proj',
    )
    expect(opts[0].suggested).toBe(true)
    expect(opts[0].target).toEqual({ feature: 'beta', board: 'feature', scope: 'beta' })
    // Global + Project + both features are all offered as destinations.
    expect(opts.map((o) => o.key)).toEqual(
      expect.arrayContaining(['global', 'project', 'feature:alpha', 'feature:beta']),
    )
  })

  it('offers all boards (none pre-suggested) for a non-feature artifact', () => {
    const opts = buildBoardTargets('C:/proj/README.md', ['alpha'], 'C:/proj')
    // global is the path-derived target here, so it is the hoisted/suggested one.
    expect(opts[0].target.board).toBe('global')
    expect(opts.some((o) => o.key === 'feature:alpha')).toBe(true)
  })
})
