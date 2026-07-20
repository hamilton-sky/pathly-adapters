// builtinSystemPrompts — the app-shipped prompt presets (analyze / split / comment / diagram),
// surfaced READ-ONLY in the Library's System group.
//
// WHY this exists: the editor + Sections selections show a MERGE of these client-shipped
// builtins with the user's DB rows (see useMergedPresets). The Library, though, reads only the
// DB — so the built-in presets a user sees in those dropdowns were invisible here. Folding them
// in (flagged readOnly, so ItemRow hides delete/rename/move) makes the Library the full picture:
// the same set as the selections, with the user's own rows layered on top. They stay client
// constants (not prompt_library rows) so app updates keep shipping new/edited defaults.

import type { CatalogItemData } from './useCatalogData'
import type { PromptPreset } from '../PromptActionConfig/presetTypes'
import { SPLIT_PRESETS, ANALYZE_LENSES } from '../../MarkdownEditor/EditorHeader/actionPresets'
import { DIAGRAM_PRESETS } from '../../MarkdownEditor/EditorHeader/diagramPresets'
import { COMMENT_VERBS } from '../../Editor/commentVerbs'

function toItems(presets: PromptPreset[], category: string): CatalogItemData[] {
  return presets.map((p) => ({
    name: p.label || p.name || category,
    description: p.hint || undefined,
    category,
    itemType: 'system' as const,
    readOnly: true,
    body: p.prompt,
  }))
}

/** The full built-in set, keyed to the System group's fixed categories. */
export const BUILTIN_SYSTEM_ITEMS: CatalogItemData[] = [
  ...toItems(ANALYZE_LENSES, 'analyze'),
  ...toItems(SPLIT_PRESETS, 'split'),
  ...toItems(COMMENT_VERBS, 'comment'),
  ...toItems(DIAGRAM_PRESETS, 'diagram'),
]
