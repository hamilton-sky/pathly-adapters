/* ─── diffUtils — diff algorithms for the Draft Diff Viewer ───────
   Two granularities:
     • computeLineDiff — line-level (use for code blocks)
     • computeWordDiff — word-level (RECOMMENDED for markdown prose;
       highlights the individual words that changed inside a section)
   Both are LCS-based and share the generic `lcs` backtracker below. */

export type DiffOpType = 'same' | 'remove' | 'add'

export interface DiffLine {
  type: DiffOpType
  text: string
}

export interface WordToken {
  type: DiffOpType
  text: string
}

const MAX_LINES = 600
const MAX_TOKENS = 4000

interface LcsOp<T> {
  type: DiffOpType
  value: T
}

/** Generic longest-common-subsequence diff over two arrays. */
function lcs<T>(a: T[], b: T[]): LcsOp<T>[] {
  const m = a.length
  const n = b.length
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array<number>(n + 1).fill(0))
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = a[i - 1] === b[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1])
    }
  }

  const out: LcsOp<T>[] = []
  let i = m
  let j = n
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      out.unshift({ type: 'same', value: a[i - 1] })
      i--
      j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      out.unshift({ type: 'add', value: b[j - 1] })
      j--
    } else {
      out.unshift({ type: 'remove', value: a[i - 1] })
      i--
    }
  }
  return out
}

/** Line-level diff. Best for code or any content where line identity matters. */
export function computeLineDiff(original: string | null, draft: string | null): DiffLine[] {
  if (!original && !draft) return []
  if (!original) return (draft ?? '').split('\n').map((text) => ({ type: 'add' as const, text }))
  if (!draft) return original.split('\n').map((text) => ({ type: 'remove' as const, text }))

  const a = original.split('\n').slice(0, MAX_LINES)
  const b = draft.split('\n').slice(0, MAX_LINES)
  return lcs(a, b).map(({ type, value }) => ({ type, text: value }))
}

/** Split text into word + whitespace tokens (whitespace preserved as its own token). */
function tokenizeWords(text: string): string[] {
  return text.match(/\s+|\S+/g) ?? []
}

/**
 * Word-level diff — recommended for markdown prose. Returns a flat token
 * stream so a single paragraph can be rendered once with only the changed
 * words highlighted, instead of a whole-line add/remove block.
 */
export function computeWordDiff(original: string | null, draft: string | null): WordToken[] {
  const a = tokenizeWords(original ?? '')
  const b = tokenizeWords(draft ?? '')

  // Guard against pathological inputs — fall back to a coarse line diff.
  if (a.length > MAX_TOKENS || b.length > MAX_TOKENS) {
    return computeLineDiff(original, draft).flatMap((l, idx, arr) => {
      const token: WordToken = { type: l.type, text: l.text }
      return idx < arr.length - 1 ? [token, { type: 'same', text: '\n' }] : [token]
    })
  }

  return lcs(a, b).map(({ type, value }) => ({ type, text: value }))
}

export interface WordChangeCount {
  added: number
  removed: number
}

/** Count changed words between two texts — for the triage row's +N / -N stat. */
export function countWordChanges(original: string | null, draft: string | null): WordChangeCount {
  const toks = computeWordDiff(original, draft)
  return {
    added: toks.filter((t) => t.type === 'add' && /\S/.test(t.text)).length,
    removed: toks.filter((t) => t.type === 'remove' && /\S/.test(t.text)).length,
  }
}
