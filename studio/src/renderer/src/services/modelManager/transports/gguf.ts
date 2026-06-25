// GGUF / node-llama-cpp transport (one-shot).
//
// Reuses the EXACT renderer bridge primitives that HQ uses for GGUF chat:
//   - `getEngine(modelId)`  → window.pathly.llm.load (ensures the model is loaded)
//   - `askLlm(prompt, systemPrompt, onChunk)` → window.pathly.llm.chat, which
//     streams tokens via onToken/onDone and resolves with the full text.
// HQ (`useHQ.tsx`) calls these same two functions in sequence; here we simply
// accumulate the stream into a single string instead of feeding the chat UI.

import { getEngine, askLlm } from '../../../lib/llmBridge'
import type { RunResult } from './types'

export async function runGguf(modelId: string, prompt: string): Promise<RunResult> {
  // Ensure the GGUF model is loaded into memory (mirrors HQ's `await getEngine(...)`).
  await getEngine(modelId)
  // askLlm resolves with the full accumulated text once `llm:done` fires.
  // onChunk is a no-op for one-shot use — we only need the final string.
  const text = await askLlm(prompt, '', () => {})
  return { text }
}
