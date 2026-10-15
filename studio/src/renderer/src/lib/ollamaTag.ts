/** Whether Ollama has *tag* installed (`qwen3:8b` matches `qwen3:8b`,
 *  `qwen3:latest` or `qwen3-…`) — i.e. whether HQ answers through Ollama
 *  rather than the built-in runtime. */
export function ollamaHasTag(tag: string, installed: string[]): boolean {
  if (!tag) return false
  const base = tag.split(':')[0]
  return installed.some((m) => m === tag || m.startsWith(base + ':') || m.startsWith(base + '-'))
}
