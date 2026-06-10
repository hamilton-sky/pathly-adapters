import type { Comment } from './useComments'

export function deriveLineNumber(fileBody: string, anchorText: string): number {
  const lines = fileBody.split('\n')
  const firstLine = anchorText.split('\n')[0].trim()
  const idx = lines.findIndex((l) => l.includes(firstLine))
  return idx !== -1 ? idx + 1 : 1
}

export function getSpawnCwd(filePath: string): string {
  const norm = filePath.replace(/\\/g, '/')
  const planIdx = norm.indexOf('/pathly/plans/')
  return planIdx !== -1 ? norm.slice(0, planIdx) : norm.slice(0, norm.lastIndexOf('/'))
}

export function buildSendPrompt(filePath: string, body: string, unresolved: Comment[]): string {
  const norm = filePath.replace(/\\/g, '/')
  const commentLines = unresolved
    .map((c) => `Line ${c.lineNumber} ("${c.lineText.slice(0, 60).trim()}"): ${c.body}`)
    .join('\n')
  return [
    `You are revising the file: ${norm}`,
    '',
    'Address each reviewer comment below. Do not change sections that have no comments.',
    'Do not ask clarifying questions. Make your best interpretation of each comment and apply it directly.',
    '',
    '--- REVIEWER COMMENTS ---',
    commentLines,
    '---',
    '',
    '--- CURRENT FILE CONTENT ---',
    body,
    '---',
    '',
    `Write the complete revised content to: ${norm}.draft`,
    'Do not write anything else — only the file content goes to that path. Exit when done.',
  ].join('\n')
}
