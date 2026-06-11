import type { Comment } from './useComments'

export function buildSplitPrompt(filePath: string): string {
  const norm = filePath.replace(/\\/g, '/')
  return [
    `You are restructuring a Pathly skill file into well-organized sections.`,
    ``,
    `Read the file at: ${norm}`,
    ``,
    `Analyze the content and identify natural split points. Each logical concern, phase, or topic`,
    `should become its own ## section — small enough to be an independent cell in the skill editor.`,
    ``,
    `Rules:`,
    `- Preserve all existing content exactly — do not rewrite, add, or remove instructions`,
    `- Group related paragraphs under a single ## heading`,
    `- Use short, descriptive ## headings (3–5 words)`,
    `- Maintain the original logical order`,
    `- If the content already has ## sections, refine them for better granularity`,
    ``,
    `Write the restructured content to: ${norm}.draft`,
    ``,
    `Do not write anything else. Exit when done.`,
  ].join('\n')
}

export function buildAnalyzePrompt(filePath: string): string {
  const norm = filePath.replace(/\\/g, '/')
  return [
    `You are reviewing a Pathly skill file for quality.`,
    ``,
    `Read the file at: ${norm}`,
    ``,
    `Write an analysis report to: ${norm}.analysis`,
    ``,
    `Format your report as markdown with these sections:`,
    ``,
    `## Summary`,
    `1–2 sentence overview of what this skill does.`,
    ``,
    `## Strengths`,
    `What this skill does well — clear instructions, good structure, appropriate scope.`,
    ``,
    `## Gaps & Ambiguities`,
    `Unclear instructions, missing edge cases, or steps that could be misinterpreted.`,
    `Reference exact phrases or sections where possible.`,
    ``,
    `## Redundancies`,
    `Verbose or repeated sections that could be tightened without losing meaning.`,
    ``,
    `## Suggested Improvements`,
    `Concrete, actionable changes ranked by impact. 1–2 sentences each.`,
    ``,
    `## Token Estimate`,
    `Rough token cost per invocation and whether it is appropriate for the task complexity.`,
    ``,
    `Do not write anything else. Exit when done.`,
  ].join('\n')
}

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

export const STORAGE_KEY_SPLIT   = 'pathly:prompt_override_split'
export const STORAGE_KEY_ANALYZE = 'pathly:prompt_override_analyze'

export function getEffectivePrompt(
  builder: (path: string) => string,
  storageKey: string,
  filePath: string,
): string {
  try {
    const saved = localStorage.getItem(storageKey)
    return saved ?? builder(filePath)
  } catch {
    return builder(filePath)
  }
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
