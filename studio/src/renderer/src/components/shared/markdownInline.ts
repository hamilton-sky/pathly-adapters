// Pure inline-formatting transforms shared by the cell notebook (textarea) and the
// CodeMirror source editor. No React, no DOM — just (text, selection) → (text, selection).
// One module, two dispatch sites, so both views emit byte-identical markdown.

export interface InlineEdit {
  text: string
  selStart: number
  selEnd: number
}

/**
 * Toggle a paired marker (`**`, `_`, `` ` ``) around the selection.
 * - markers already just outside the selection → unwrap
 * - markers inside the selection → unwrap
 * - otherwise → wrap, leaving the inner text selected
 * Works with an empty selection (inserts the pair, cursor between the markers).
 */
function toggle(text: string, selStart: number, selEnd: number, prefix: string, suffix: string): InlineEdit {
  const before = text.slice(0, selStart)
  const selected = text.slice(selStart, selEnd)
  const after = text.slice(selEnd)

  // Already wrapped just outside the selection → unwrap
  if (before.endsWith(prefix) && after.startsWith(suffix)) {
    const newStart = selStart - prefix.length
    return {
      text: before.slice(0, before.length - prefix.length) + selected + after.slice(suffix.length),
      selStart: newStart,
      selEnd: newStart + selected.length,
    }
  }

  // Markers sit inside the selection → unwrap
  if (selected.length >= prefix.length + suffix.length && selected.startsWith(prefix) && selected.endsWith(suffix)) {
    const inner = selected.slice(prefix.length, selected.length - suffix.length)
    return { text: before + inner + after, selStart, selEnd: selStart + inner.length }
  }

  // Otherwise wrap
  return {
    text: before + prefix + selected + suffix + after,
    selStart: selStart + prefix.length,
    selEnd: selStart + prefix.length + selected.length,
  }
}

export type InlineFormat = 'bold' | 'italic' | 'code'

export function applyInlineFormat(format: InlineFormat, text: string, selStart: number, selEnd: number): InlineEdit {
  switch (format) {
    case 'bold':   return toggle(text, selStart, selEnd, '**', '**')
    case 'italic': return toggle(text, selStart, selEnd, '_', '_')
    case 'code':   return toggle(text, selStart, selEnd, '`', '`')
  }
}
