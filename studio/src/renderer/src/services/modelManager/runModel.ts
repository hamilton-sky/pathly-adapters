// One-shot run entry point — dispatches a prompt to the right transport by id.
//
// Transport selection mirrors HQ's send path (`useHQ.tsx > handleSend`):
//   - id === 'brightsky'                         → Brightsky WS  (runBrightsky)
//   - catalog model, Ollama tag installed/running → Ollama HTTP   (runOllama)
//   - catalog model, GGUF cached + llm available  → node-llama-cpp (runGguf)
// HQ decides Ollama-vs-GGUF from live store state (`ollamaModelIds`,
// `cachedModelIds`, `llmAvailable`); the same signals are consulted here so a
// caller that just passes an id gets the transport HQ would have used.

import { useModelStore } from '../../store/modelStore'
import { BRIGHTSKY_ID, getModelById } from './catalog'
import { runOllama } from './transports/ollama'
import { runGguf } from './transports/gguf'
import { runBrightsky } from './transports/brightsky'
import type { RunResult } from './transports/types'

export type { RunResult }

function ollamaHasTag(ollamaTag: string): boolean {
  if (!ollamaTag) return false
  const base = ollamaTag.split(':')[0]
  return useModelStore
    .getState()
    .ollamaModelIds.some((m) => m === ollamaTag || m.startsWith(base + ':') || m.startsWith(base + '-'))
}

/**
 * Run `prompt` against the model identified by `id` and resolve with the result.
 *
 * @param id     catalog model id (e.g. 'phi-4-mini') or 'brightsky'
 * @param prompt the full user/system prompt to send (no system-prompt arg —
 *               callers fold any system context into `prompt`)
 */
export async function runModel(id: string, prompt: string): Promise<RunResult> {
  if (id === BRIGHTSKY_ID) {
    return runBrightsky(prompt)
  }

  const model = getModelById(id)
  if (!model) {
    throw new Error(`Unknown model id: ${id}`)
  }

  const state = useModelStore.getState()
  const ollamaTag = model.ollamaId
  const ollamaInstalled = state.ollamaAvailable === true && ollamaHasTag(ollamaTag)

  if (ollamaInstalled) {
    return runOllama(ollamaTag, prompt)
  }

  if (state.cachedModelIds.includes(id)) {
    return runGguf(id, prompt)
  }

  // Neither backend has the model ready. Prefer Ollama if it's running (the tag
  // can still be served if present); otherwise fail with an actionable message.
  if (state.ollamaAvailable === true && ollamaTag) {
    return runOllama(ollamaTag, prompt)
  }

  throw new Error(
    `Model '${id}' is not available — install it via Ollama (\`ollama pull ${ollamaTag || id}\`) or download the GGUF first.`
  )
}
