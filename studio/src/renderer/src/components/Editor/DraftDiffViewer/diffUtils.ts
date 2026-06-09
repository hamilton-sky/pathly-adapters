export type DiffLine = { type: 'same' | 'remove' | 'add'; text: string }

const MAX_LINES = 600

export function computeLineDiff(original: string | null, draft: string | null): DiffLine[] {
  if (!original && !draft) return []
  if (!original) return (draft ?? '').split('\n').map((text) => ({ type: 'add' as const, text }))
  if (!draft) return original.split('\n').map((text) => ({ type: 'remove' as const, text }))

  const a = original.split('\n').slice(0, MAX_LINES)
  const b = draft.split('\n').slice(0, MAX_LINES)
  return lcsDiff(a, b)
}

function lcsDiff(a: string[], b: string[]): DiffLine[] {
  const m = a.length
  const n = b.length

  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))
  for (let i = 1; i <= m; i++)
    for (let j = 1; j <= n; j++)
      dp[i][j] = a[i - 1] === b[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1])

  const result: DiffLine[] = []
  let i = m
  let j = n
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      result.unshift({ type: 'same', text: a[i - 1] })
      i--
      j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({ type: 'add', text: b[j - 1] })
      j--
    } else {
      result.unshift({ type: 'remove', text: a[i - 1] })
      i--
    }
  }

  return result
}
