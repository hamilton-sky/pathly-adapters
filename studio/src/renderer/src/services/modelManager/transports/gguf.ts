// GGUF / node-llama-cpp transport (one-shot) — artifact summaries and other
// background jobs on the built-in runtime.
//
// Goes through askLlmBackground: queued behind (and ahead of) HQ's answers, so
// the untagged llm:token stream never mixes two jobs, and on THIS model id (not
// the HQ picker's). llm:chat loads the model itself, inside the queue — a separate
// getEngine() here could swap models under an answer still generating.

import { askLlmBackground } from '../../../lib/llmBridge'
import type { RunResult } from './types'

/** One-shot settings: no reasoning (Qwen3's thought tokens count against the
 *  cap and would truncate the summary) and a context sized to the prompt — left
 *  unset, node-llama-cpp grows to the model's full window (41k, ~3.5 GB). */
export function oneShotGeneration(prompt: string): { maxTokens: number; thoughtBudget: number; contextSize: number } {
  const promptTokens = Math.ceil(prompt.length / 3) // generous: chars/4 under-counts code and Markdown
  const maxTokens = 1024
  return { maxTokens, thoughtBudget: 0, contextSize: Math.min(16384, Math.max(4096, promptTokens + maxTokens + 512)) }
}

export async function runGguf(modelId: string, prompt: string): Promise<RunResult> {
  const text = await askLlmBackground(prompt, modelId, oneShotGeneration(prompt))
  return { text }
}
