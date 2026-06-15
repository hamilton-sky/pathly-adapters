// CodeMirror extension that paints find/replace match ranges into the document.
// The MarkdownEditor handle pushes ranges in via the `setSearchMatches` effect;
// the field keeps them mapped through edits and renders two decoration variants
// (all matches dim, the active match emphasised).
import { StateField, StateEffect, RangeSetBuilder } from '@codemirror/state'
import { EditorView, Decoration } from '@codemirror/view'
import type { DecorationSet } from '@codemirror/view'
import type { MatchRange } from './searchEngine'

export const setSearchMatches = StateEffect.define<{ ranges: MatchRange[]; current: number }>()

const matchMark = Decoration.mark({ class: 'cm-find-match' })
const currentMark = Decoration.mark({ class: 'cm-find-match-current' })

export const searchHighlightField = StateField.define<DecorationSet>({
  create() {
    return Decoration.none
  },
  update(deco, tr) {
    let next = deco.map(tr.changes)
    for (const effect of tr.effects) {
      if (effect.is(setSearchMatches)) {
        const builder = new RangeSetBuilder<Decoration>()
        const { ranges, current } = effect.value
        ranges.forEach((r, i) => {
          if (r.from === r.to) return
          builder.add(r.from, r.to, i === current ? currentMark : matchMark)
        })
        next = builder.finish()
      }
    }
    return next
  },
  provide: (field) => EditorView.decorations.from(field),
})
