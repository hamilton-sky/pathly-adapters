import type { PromptPreset } from '../shared/PromptActionConfig/presetTypes'

export const COMMENT_VERBS: PromptPreset[] = [
  {
    name: '',
    label: 'Apply changes',
    hint: 'default · address each comment',
    prompt: '',
  },
  {
    name: 'explain',
    label: 'Explain',
    hint: 'explain the selected text / comments, don\'t edit',
    prompt: 'Explain the selected text and the reviewer comments. Do not make edits — write your explanation as a reply in the draft file.',
  },
  {
    name: 'find',
    label: 'Find similar',
    hint: 'find similar passages elsewhere in the file',
    prompt: 'Find passages elsewhere in the file that are similar to the commented section. List them with line references in the draft file. Do not make edits.',
  },
  {
    name: 'ask',
    label: 'Answer question',
    hint: 'answer the question in the comment',
    prompt: 'Answer the question posed in the reviewer comment. Write your answer in the draft file. Do not make edits to the source content.',
  },
]
