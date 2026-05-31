import type { buildPathlyContext } from '../../lib/pathlyContext'

export function stripAnsi(raw: string): string {
  return raw
    // OSC sequences: ESC ] ... BEL or ST
    .replace(/\x1b\][\s\S]*?(?:\x07|\x1b\\)/g, '')
    // DCS / SOS / PM / APC: ESC [P X ^ _] ... ST
    .replace(/\x1b[PX^_][\s\S]*?\x1b\\/g, '')
    // CSI sequences: ESC [ params final-byte (0x40–0x7e)
    .replace(/\x1b\[[\x20-\x3f]*[\x40-\x7e]/g, '')
    // Any remaining ESC + one char
    .replace(/\x1b./g, '')
    // C0 control chars except BS (\x08), CR (\r), LF (\n), TAB (\t)
    // \x08 is intentionally kept — feedBuffer handles it as a backspace/erase
    .replace(/[\x00-\x07\x0b\x0c\x0e-\x1f\x7f]/g, '')
    // NOTE: \r is intentionally NOT stripped here — handled in feedBuffer below
}

/** Returns true for noisy progress/spinner lines that should not appear in the snippet */
export function isNoisyLine(line: string): boolean {
  if (line.length <= 2) return true
  if (/^Working\s*\(/.test(line)) return true
  if (/^[-─-╿\s]+$/.test(line)) return true
  return false
}

/**
 * Feed a raw PTY chunk into a per-target line buffer with correct \r semantics.
 * \r alone = "go to start of current line" (overwrite), not a line terminator.
 * This prevents partial-word artifacts from spinner/progress lines.
 */
export function feedBuffer(buf: string, data: string): { buf: string; lines: string[] } {
  const stripped = stripAnsi(data)
  // Normalise Windows \r\n → \n first, then handle lone \r as overwrite
  const normalized = stripped.replace(/\r\n/g, '\n')
  const segments = normalized.split('\r')

  let current = buf
  for (let i = 0; i < segments.length; i++) {
    if (i > 0) {
      // Lone \r: discard current partial line back to last \n
      const lastNl = current.lastIndexOf('\n')
      current = lastNl >= 0 ? current.slice(0, lastNl + 1) : ''
    }
    // Apply segment char-by-char so \x08 (backspace) erases the previous character
    for (const ch of segments[i]) {
      if (ch === '\x08') {
        // Erase last non-newline character in the current partial line
        const lastNl = current.lastIndexOf('\n')
        if (current.length > lastNl + 1) current = current.slice(0, -1)
      } else {
        current += ch
      }
    }
  }

  const parts = current.split('\n')
  const remaining = parts.pop() ?? ''
  const lines: string[] = []
  for (const line of parts) {
    const trimmed = line.trim()
    if (trimmed.length > 0 && !isNoisyLine(trimmed)) lines.push(trimmed)
  }
  return { buf: remaining, lines }
}

export function buildSystemPrompt(
  context: Awaited<ReturnType<typeof buildPathlyContext>>,
  topMatch: { skill: string; confidence: number; command: string; description: string } | null
): string {
  const skillList = context.skills.join(', ')
  const stageInfo = context.fsmStage !== 'unknown' && context.fsmStage
    ? `Current pipeline stage: ${context.fsmStage}${context.featureName ? ` (feature: ${context.featureName})` : ''}.`
    : 'No active pipeline stage.'

  if (topMatch && topMatch.confidence >= 0.4) {
    return `You are Conductor in Pathly Studio. Answer questions about Pathly skills using only the information given to you. Do not invent details.`
  }

  const schemaInfo = context.studioSchema && context.studioSchema.length > 0
    ? `\n\n## Studio UI Elements\n${context.studioSchema.slice(0, 20).map((el) => `- ${el.screen}: ${el.label} (${el.type})`).join('\n')}`
    : ''
  const menuInfo = context.menu
    ? `\n\n## Current Menu\nState: ${context.menu.state}\nTitle: ${context.menu.title}\n${context.menu.items.map((item) => `- ${item.label}: ${item.command} (${item.description})`).join('\n')}`
    : ''

  return `You are the Conductor — a helpful AI assistant built into Pathly Studio.
Your job is to help users run Pathly pipeline skills and navigate the Studio UI.

${stageInfo}
Available skills: ${skillList}
No strong skill match found.${schemaInfo}${menuInfo}

When a user asks about running a skill, explain what it does and confirm the match.
Be concise (2-3 sentences). Do not invent skills that are not in the available list.`
}
