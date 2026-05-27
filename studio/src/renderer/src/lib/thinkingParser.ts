/**
 * Splits streamed LLM text into thinking (inside <think>...</think>) and visible content.
 * Works on the full accumulated text each token — safe for mid-tag streaming.
 */
export function splitThinkingContent(text: string): { thinking: string; content: string } {
  const thinkingParts: string[] = []
  let content = text

  // Extract completed <think>...</think> blocks
  content = content.replace(/<think>([\s\S]*?)<\/think>/g, (_, inner) => {
    thinkingParts.push(inner.trim())
    return ''
  })

  // Handle an unclosed <think> block still streaming
  const openIdx = content.lastIndexOf('<think>')
  if (openIdx !== -1) {
    thinkingParts.push(content.slice(openIdx + 7))
    content = content.slice(0, openIdx)
  }

  return {
    thinking: thinkingParts.join('\n\n').trim(),
    content: content.trim(),
  }
}
