// Ollama transport (one-shot).
//
// HQ chat streams via `askOllama(...)` → `window.pathly.llm.ollamaChat` (main),
// which POSTs http://localhost:11434/api/generate with stream:true. For a
// one-shot, non-streaming run we POST the same endpoint directly with
// stream:false — exactly like the Python reference `runner/inference.py`
// `_run_ollama` (POST http://127.0.0.1:11434/api/generate, {model, prompt,
// stream:false}, read body.response). This keeps `runModel` self-contained and
// avoids threading a one-shot flag through the streaming IPC channel.

import type { RunResult } from './types'

const OLLAMA_GENERATE_URL = 'http://127.0.0.1:11434/api/generate'

interface OllamaGenerateResponse {
  response?: string
}

/**
 * Run a single non-streaming completion against a local Ollama model.
 * @param ollamaTag the Ollama model tag (e.g. 'phi4-mini:latest')
 */
export async function runOllama(ollamaTag: string, prompt: string): Promise<RunResult> {
  const res = await fetch(OLLAMA_GENERATE_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: ollamaTag, prompt, stream: false }),
  })
  if (!res.ok) {
    throw new Error(`Ollama error ${res.status}: ${await res.text()}`)
  }
  const body = (await res.json()) as OllamaGenerateResponse
  return { text: (body.response ?? '').trim() }
}
