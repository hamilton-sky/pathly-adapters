import type { Comment } from './useComments'
import { resolvePrompt } from '../shared/PromptActionConfig/presetTypes'
import type { PromptPreset } from '../shared/PromptActionConfig/presetTypes'

export const SPLIT_PROMPT_TEMPLATE = [
  `You are restructuring a Pathly skill file into well-organized sections.`,
  ``,
  `Read the file at: {{FILE}}`,
  ``,
  `Analyze the content and identify natural split points. Each logical concern, phase, or topic`,
  `should become its own ## section — small enough to be an independent cell in the skill editor.`,
  ``,
  `Rules:`,
  `- Preserve all existing content exactly — do not rewrite, add, or remove instructions`,
  `- Preserve every character byte-for-byte, including Unicode punctuation (em-dash —, en-dash –,`,
  `  curly quotes ' ' " ", ellipsis …). Never substitute or re-encode them.`,
  `- Group related paragraphs under a single ## heading`,
  `- Use short, descriptive ## headings (3–5 words)`,
  `- Maintain the original logical order`,
  `- If the content already has ## sections, refine them for better granularity`,
  ``,
  `Write the restructured content to: {{FILE}}.split.draft`,
  `Write the file as UTF-8 using your native file-writing tool. Do NOT route content through shell`,
  `commands (Get-Content/Set-Content/Out-File or > redirection) — on Windows PowerShell they corrupt`,
  `Unicode into mojibake (— becomes "â€").`,
  ``,
  `Do not write anything else. Exit when done.`,
].join('\n')

export const ANALYZE_PROMPT_TEMPLATE = [
  `You are reviewing a Pathly skill file for quality.`,
  ``,
  `Read the file at: {{FILE}}`,
  ``,
  `Write an analysis report to: {{FILE}}.analysis`,
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
  `Write the report as UTF-8 using your native file-writing tool — do NOT route it through shell`,
  `commands (Get-Content/Set-Content/Out-File or > redirection), which corrupt Unicode on Windows.`,
  `Do not write anything else. Exit when done.`,
].join('\n')

export function buildSplitPrompt(filePath: string): string {
  const norm = filePath.replace(/\\/g, '/')
  return resolvePrompt(SPLIT_PROMPT_TEMPLATE, { FILE: norm })
}

export function buildAnalyzePrompt(filePath: string): string {
  const norm = filePath.replace(/\\/g, '/')
  return resolvePrompt(ANALYZE_PROMPT_TEMPLATE, { FILE: norm })
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

const snippet = (s: string, n = 160): string => (s.length > n ? s.slice(0, n - 1) + '…' : s)

// Turn an opaque "no file" failure into a specific, actionable reason using the engine's
// exit code and last output — so rate limits, auth errors, and "agent wrote nothing" are
// distinguishable instead of all reading "no draft produced". Shared by AI Split/Analyze
// (useEditorAgentActions) and the comments Send flow (CommentsPanel).
export function describeAgentFailure(action: string, fileName: string, exitCode?: number, tail?: string): string {
  const last = (tail ?? '').trim()
  const low = last.toLowerCase()
  if (/rate.?limit|usage limit|quota|429|too many requests|overloaded/.test(low))
    return `${action} failed · ${fileName} — rate limit / quota${last ? `: ${snippet(last)}` : ''}`
  if (/unauthor|not logged in|please log in|\blog ?in\b|api key|credential|forbidden|\b401\b|\b403\b/.test(low))
    return `${action} failed · ${fileName} — auth / login needed${last ? `: ${snippet(last)}` : ''}`
  if (typeof exitCode === 'number' && exitCode !== 0)
    return `${action} failed · ${fileName} — engine exited (code ${exitCode})${last ? `: ${snippet(last)}` : ''}`
  return last
    ? `${action} failed · ${fileName} — no file written; engine said: ${snippet(last)}`
    : `${action} failed · ${fileName} — no file produced (engine wrote nothing)`
}

export function buildSendPrompt(filePath: string, body: string, unresolved: Comment[], verb?: PromptPreset, extra?: string): string {
  const norm = filePath.replace(/\\/g, '/')
  const commentLines = unresolved
    .map((c) => `Line ${c.lineNumber} ("${c.lineText.slice(0, 60).trim()}"): ${c.body}`)
    .join('\n')

  const useDefault = !verb || verb.name === ''

  const baseInstruction = useDefault
    ? [
        'Address each reviewer comment below. Do not change sections that have no comments.',
        'Do not ask clarifying questions. Make your best interpretation of each comment and apply it directly.',
        'Preserve every character byte-for-byte in untouched text, including Unicode punctuation',
        '(em-dash, curly quotes, ellipsis). Never substitute or re-encode them.',
      ].join('\n')
    : verb.prompt

  // Extra instructions are appended only when present, so the default send stays byte-identical.
  const instruction = extra && extra.trim()
    ? `${baseInstruction}\n\nAdditional instructions:\n${extra.trim()}`
    : baseInstruction

  return [
    `You are revising the file: ${norm}`,
    '',
    instruction,
    '',
    '--- REVIEWER COMMENTS ---',
    commentLines,
    '---',
    '',
    '--- CURRENT FILE CONTENT ---',
    body,
    '---',
    '',
    `Write the complete revised content to: ${norm}.comments.draft`,
    'Write the file as UTF-8 using your native file-writing tool. Do NOT route content through shell',
    'commands (Get-Content/Set-Content/Out-File or > redirection) — on Windows PowerShell they corrupt',
    'Unicode into mojibake.',
    'Do not write anything else — only the file content goes to that path. Exit when done.',
  ].join('\n')
}
